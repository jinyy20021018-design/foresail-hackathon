import os

from app.services.news_event_extractor import extract_event_from_news_item
from app.services.rss_search_service import fetch_rss_items, filter_rss_items
from app.services.search_query_builder import build_external_event_queries


class RealSearchEventConnector:
    name = "real_search_event_connector"

    def __init__(self) -> None:
        self.last_result: dict = {}

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        queries = build_external_event_queries(case_id, watch_profile)
        if os.getenv("REAL_SEARCH_ENABLED", "false").lower() != "true":
            self.last_result = _summary(queries, warnings=["Real search connector disabled."], enabled=False)
            return []

        feed_urls = _feed_urls()
        if not feed_urls:
            self.last_result = _summary(queries, warnings=["No RSS feed URLs configured for real search."], enabled=True)
            return []

        timeout_seconds = _int_env("REAL_SEARCH_TIMEOUT_SECONDS", 10)
        max_results = _int_env("REAL_SEARCH_MAX_RESULTS_PER_QUERY", 5)
        rss_items, feed_errors = fetch_rss_items(feed_urls, timeout_seconds)
        matched_items = filter_rss_items(rss_items, queries, watch_profile, max_results)
        events = []
        extraction_errors = []
        for item in matched_items:
            try:
                event = extract_event_from_news_item(item, watch_profile)
                if event:
                    events.append(event)
            except Exception as error:
                extraction_errors.append({"title": item.get("rss_item", {}).get("title"), "error": str(error)})
        self.last_result = {
            "enabled": True,
            "queries_generated": len(queries),
            "feeds_checked": len(feed_urls),
            "rss_items_fetched": len(rss_items),
            "rss_items_matched": len(matched_items),
            "events_extracted": len(events),
            "connector_errors": feed_errors + extraction_errors,
            "warnings": [],
            "queries": queries,
        }
        return events


def _summary(queries: list[dict], warnings: list[str], enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "queries_generated": len(queries),
        "feeds_checked": 0,
        "rss_items_fetched": 0,
        "rss_items_matched": 0,
        "events_extracted": 0,
        "connector_errors": [],
        "warnings": warnings,
        "queries": queries,
    }


def _feed_urls() -> list[str]:
    return [url.strip() for url in os.getenv("REAL_SEARCH_FEED_URLS", "").split(",") if url.strip()]


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
