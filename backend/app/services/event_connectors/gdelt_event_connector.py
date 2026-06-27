import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from app.services.news_event_extractor import extract_event_from_gdelt_article
from app.services.search_query_builder import build_external_event_queries


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
        articles_fetched = 0
        max_total = _int_env("REAL_EVENT_MAX_TOTAL_RESULTS", 30)
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
            except Exception as error:
                connector_errors.append({"query_id": query.get("query_id"), "query": query.get("query_text"), "error": str(error)})

        self.last_result = {
            "enabled": True,
            "queries_generated": len(queries),
            "articles_fetched": articles_fetched,
            "events_extracted": len(events),
            "connector_errors": connector_errors,
            "warnings": [],
            "queries": queries,
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
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "ForeSail-MVP/3.1"})
    with urllib.request.urlopen(request, timeout=_int_env("GDELT_TIMEOUT_SECONDS", 10)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    articles = payload.get("articles") or []
    if not isinstance(articles, list):
        raise ValueError("GDELT response did not contain an articles list.")
    return [article for article in articles if isinstance(article, dict)]


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
    }


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
