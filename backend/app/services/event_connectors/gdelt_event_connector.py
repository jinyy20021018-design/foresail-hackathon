import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from time import time

from app.services.news_event_extractor import extract_event_from_gdelt_article
from app.services.search_query_builder import build_external_event_queries


class GdeltRateLimited(RuntimeError):
    pass


class GdeltFetchError(RuntimeError):
    pass


_ARTICLE_CACHE: dict[str, tuple[float, list[dict]]] = {}


class GdeltEventConnector:
    name = "gdelt_event_connector"

    def __init__(self) -> None:
        self.last_result: dict = {}

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        queries = [query for query in build_external_event_queries(case_id, watch_profile) if _is_gdelt_query(query)]
        if os.getenv("GDELT_ENABLED", "false").lower() != "true":
            self.last_result = _summary(queries, warnings=["GDELT connector disabled."], enabled=False)
            return []

        events: list[dict] = []
        connector_errors: list[dict] = []
        warnings: list[str] = []
        articles_fetched = 0
        max_total = _int_env("REAL_EVENT_MAX_TOTAL_RESULTS", 30)
        rate_limited = False

        for query in queries:
            if len(events) >= max_total:
                break
            try:
                articles = _fetch_articles(query)
                articles_fetched += len(articles)
                for article in articles:
                    event = extract_event_from_gdelt_article(article, query, watch_profile)
                    if event:
                        events.append(event)
                    if len(events) >= max_total:
                        break
            except GdeltRateLimited as error:
                rate_limited = True
                warning = str(error)
                if warning not in warnings:
                    warnings.append(warning)
                if _bool_env("GDELT_STOP_ON_RATE_LIMIT", True):
                    break
            except Exception as error:
                connector_errors.append({"query_id": query.get("query_id"), "query": query.get("query_text"), "error": str(error)})

        self.last_result = {
            "enabled": True,
            "queries_generated": len(queries),
            "articles_fetched": articles_fetched,
            "events_extracted": len(events),
            "connector_errors": connector_errors,
            "warnings": warnings,
            "queries": queries,
            "rate_limited": rate_limited,
        }
        return events


def _fetch_articles(query: dict) -> list[dict]:
    base_url = os.getenv("GDELT_BASE_URL", "https://api.gdeltproject.org/api/v2/doc/doc")
    lookback_days = _int_env("GDELT_LOOKBACK_DAYS", 7)
    now = datetime.now(UTC)
    params = {
        "query": query["query_text"],
        "mode": "ArtList",
        "format": "json",
        "maxrecords": _int_env("GDELT_MAX_RECORDS", 10),
        "sort": "DateDesc",
        "startdatetime": (now - timedelta(days=lookback_days)).strftime("%Y%m%d%H%M%S"),
        "enddatetime": now.strftime("%Y%m%d%H%M%S"),
    }
    cache_key = json.dumps({"base_url": base_url, "params": params}, sort_keys=True)
    cached = _ARTICLE_CACHE.get(cache_key)
    cache_ttl = _int_env("GDELT_CACHE_TTL_SECONDS", 900)
    if cached and time() - cached[0] <= cache_ttl:
        return cached[1]

    payload = _open_gdelt_json(base_url, params)
    articles = payload.get("articles") or []
    if not isinstance(articles, list):
        raise ValueError("GDELT response did not contain an articles list.")
    parsed = [article for article in articles if isinstance(article, dict)]
    _ARTICLE_CACHE[cache_key] = (time(), parsed)
    return parsed


def _open_gdelt_json(base_url: str, params: dict) -> dict:
    urls = _candidate_urls(base_url, params)
    last_error: Exception | None = None
    for url in urls:
        request = urllib.request.Request(url, headers={"User-Agent": "ForeSail-MVP/3.1"})
        try:
            with urllib.request.urlopen(request, timeout=_int_env("GDELT_TIMEOUT_SECONDS", 10)) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise GdeltRateLimited(
                    "GDELT_RATE_LIMITED: GDELT returned 429 Too Many Requests. Try again later or use RSS fallback."
                ) from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            last_error = error
    raise GdeltFetchError(f"GDELT_FETCH_FAILED: {last_error}") from last_error


def _candidate_urls(base_url: str, params: dict) -> list[str]:
    encoded = urllib.parse.urlencode(params)
    urls = [f"{base_url}?{encoded}"]
    if base_url.startswith("https://") and _bool_env("GDELT_HTTP_FALLBACK_ENABLED", True):
        urls.append(f"{base_url.replace('https://', 'http://', 1)}?{encoded}")
    return urls


def _is_gdelt_query(query: dict) -> bool:
    return str(query.get("source_hint") or "GDELT").upper() != "OPEN_METEO"


def _summary(queries: list[dict], warnings: list[str], enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "queries_generated": len(queries),
        "articles_fetched": 0,
        "events_extracted": 0,
        "connector_errors": [],
        "warnings": warnings,
        "queries": queries,
        "rate_limited": False,
    }


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}
