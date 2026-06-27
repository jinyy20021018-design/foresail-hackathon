import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime


@dataclass
class RssItem:
    title: str
    summary: str | None
    published_at: str | None
    link: str | None
    source_feed: str
    raw_payload: dict


@dataclass
class MatchedRssItem:
    rss_item: dict
    matched_query_ids: list[str]
    matched_terms: list[str]
    match_score: float


def fetch_rss_items(feed_urls: list[str], timeout_seconds: int) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    errors: list[dict] = []
    for feed_url in feed_urls:
        try:
            request = urllib.request.Request(feed_url, headers={"User-Agent": "ForeSail-MVP/3.1"})
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                content = response.read()
            items.extend(_parse_feed(content, feed_url))
        except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as error:
            errors.append({"feed_url": feed_url, "error": str(error)})
    return items, errors


def filter_rss_items(items: list[dict], queries: list[dict], watch_profile: dict, max_results_per_query: int) -> list[dict]:
    matched: list[dict] = []
    seen_links: set[str] = set()
    for query in queries:
        count_for_query = 0
        terms = _terms_for_query(query["query_text"])
        for item in items:
            if count_for_query >= max_results_per_query:
                break
            text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            matched_terms = [term for term in terms if term in text]
            profile_terms = _profile_terms(watch_profile)
            profile_matches = [term for term in profile_terms if term.lower() in text]
            if not matched_terms and not profile_matches:
                continue
            link_key = item.get("link") or item.get("title")
            if link_key in seen_links:
                continue
            seen_links.add(link_key)
            count_for_query += 1
            score = min(1.0, 0.15 * len(matched_terms) + 0.2 * len(profile_matches))
            matched.append(asdict(MatchedRssItem(
                rss_item=item,
                matched_query_ids=[query["query_id"]],
                matched_terms=list(dict.fromkeys(matched_terms + profile_matches)),
                match_score=score,
            )))
    return matched


def _parse_feed(content: bytes, source_feed: str) -> list[dict]:
    root = ET.fromstring(content)
    candidates = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    items: list[dict] = []
    for element in candidates:
        title = _text(element, "title")
        summary = _text(element, "description") or _text(element, "summary") or _text(element, "{http://www.w3.org/2005/Atom}summary")
        link = _text(element, "link") or _atom_link(element)
        published_raw = _text(element, "pubDate") or _text(element, "published") or _text(element, "{http://www.w3.org/2005/Atom}published")
        items.append(asdict(RssItem(
            title=title or "Untitled RSS item",
            summary=_strip_html(summary) if summary else None,
            published_at=_parse_date(published_raw),
            link=link,
            source_feed=source_feed,
            raw_payload={"source_feed": source_feed, "published_raw": published_raw},
        )))
    return items


def _text(element: ET.Element, tag: str) -> str | None:
    found = element.find(tag)
    if found is not None and found.text:
        return found.text.strip()
    found = element.find(f".//{tag}")
    return found.text.strip() if found is not None and found.text else None


def _atom_link(element: ET.Element) -> str | None:
    found = element.find("{http://www.w3.org/2005/Atom}link")
    return found.attrib.get("href") if found is not None else None


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return value


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value).strip()


def _terms_for_query(query_text: str) -> list[str]:
    raw = re.split(r"\s+OR\s+|\s+", query_text, flags=re.IGNORECASE)
    return [term.strip("\"'(),").lower() for term in raw if len(term.strip("\"'(),")) >= 4]


def _profile_terms(watch_profile: dict) -> list[str]:
    values = [watch_profile.get("watched_vessel"), *watch_profile.get("watched_ports", []), *watch_profile.get("watched_route_regions", [])]
    return [str(value) for value in values if value and str(value) != "TBD"]
