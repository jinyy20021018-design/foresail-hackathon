import os

from app.services.event_connectors.gdelt_event_connector import GdeltEventConnector
from app.services.event_connectors.mock_event_connector import MockEventConnector
from app.services.event_connectors.open_meteo_weather_connector import OpenMeteoWeatherConnector
from app.services.event_connectors.real_search_event_connector import RealSearchEventConnector
from app.services.event_deduplicator import deduplicate_events
from app.services.event_normalizer import normalize_events
from app.services.persistence_service import list_items, save_item

VALID_MODES = {"MOCK", "REAL", "HYBRID"}


def event_source_mode() -> str:
    mode = os.getenv("EVENT_SOURCE_MODE", "REAL").upper()
    return mode if mode in VALID_MODES else "REAL"


def fetch_events_for_case(case_id: str, watch_profile: dict, agent_run_id: str | None = None, persist: bool = False) -> dict:
    mode = event_source_mode()
    connectors = _connectors_for_mode(mode)
    raw_events: list[dict] = []
    normalized_events: list[dict] = []
    connectors_called: list[str] = []
    connector_errors: list[dict] = []
    connector_results: list[dict] = []

    for connector in connectors:
        connectors_called.append(connector.name)
        try:
            connector_events = connector.fetch_events(watch_profile, case_id)
            raw_events.extend(connector_events)
            normalized_events.extend(normalize_events(connector_events, case_id, connector.name))
            if getattr(connector, "last_result", None):
                connector_results.append({"connector": connector.name, **connector.last_result})
        except Exception as error:
            connector_errors.append({"connector": connector.name, "error": str(error)})

    deduped_events, dedup_stats = deduplicate_events(normalized_events)
    if persist:
        save_external_events(case_id, deduped_events, agent_run_id)
    warnings = _mode_warnings(mode, connector_results)

    return {
        "mode": mode,
        "connectors_called": connectors_called,
        "events_raw_count": len(raw_events),
        "events_normalized_count": len(normalized_events),
        "events_deduped_count": len(deduped_events),
        "events": deduped_events,
        "connector_errors": connector_errors,
        "connector_results": connector_results,
        "search_summary": _search_summary(connector_results),
        "real_api_summary": _real_api_summary(connector_results),
        "warnings": warnings,
        "deduplication": dedup_stats,
    }


def save_external_events(case_id: str, events: list[dict], agent_run_id: str | None = None) -> None:
    for event in events:
        item = dict(event)
        item["case_id"] = case_id
        item["agent_run_id"] = agent_run_id
        save_item("external_event", _event_key(case_id, item["event_id"], agent_run_id), item, case_id)


def list_external_events(case_id: str, source_type: str | None = None, event_type: str | None = None, limit: int | None = None) -> list[dict]:
    events = [event for event in list_items("external_event", case_id) if isinstance(event, dict)]
    if source_type:
        events = [event for event in events if str(event.get("source_type", "")).upper() == source_type.upper()]
    if event_type:
        events = [event for event in events if str(event.get("event_type", "")).upper() == event_type.upper()]
    events = sorted(events, key=lambda event: event.get("created_at") or "", reverse=True)
    return events[:limit] if limit else events


def list_external_events_for_run(case_id: str, agent_run_id: str) -> list[dict]:
    return [
        event
        for event in list_external_events(case_id)
        if event.get("agent_run_id") == agent_run_id
    ]


def _connectors_for_mode(mode: str):
    if mode == "MOCK":
        return [MockEventConnector()]
    if mode == "REAL":
        return [GdeltEventConnector(), RealSearchEventConnector(), OpenMeteoWeatherConnector()]
    return [MockEventConnector(), GdeltEventConnector(), RealSearchEventConnector(), OpenMeteoWeatherConnector()]


def _event_key(case_id: str, event_id: str, agent_run_id: str | None) -> str:
    return f"{case_id}:{agent_run_id or 'FETCH'}:{event_id}"


def _search_summary(connector_results: list[dict]) -> dict:
    summary = {
        "queries_generated": 0,
        "feeds_checked": 0,
        "rss_items_fetched": 0,
        "rss_items_matched": 0,
        "events_extracted": 0,
        "connector_errors": [],
        "warnings": [],
    }
    for result in connector_results:
        if result.get("connector") != "real_search_event_connector":
            continue
        for field in ["queries_generated", "feeds_checked", "rss_items_fetched", "rss_items_matched", "events_extracted"]:
            summary[field] += int(result.get(field) or 0)
        summary["connector_errors"].extend(result.get("connector_errors") or [])
        summary["warnings"].extend(result.get("warnings") or [])
    return summary


def _real_api_summary(connector_results: list[dict]) -> dict:
    gdelt = next((result for result in connector_results if result.get("connector") == "gdelt_event_connector"), {})
    rss = next((result for result in connector_results if result.get("connector") == "real_search_event_connector"), {})
    weather = next((result for result in connector_results if result.get("connector") == "open_meteo_weather_connector"), {})
    gdelt_errors = gdelt.get("connector_errors") or []
    rss_errors = rss.get("connector_errors") or []
    weather_errors = weather.get("connector_errors") or []
    gdelt_warnings = gdelt.get("warnings") or []
    rss_warnings = rss.get("warnings") or []
    weather_warnings = weather.get("warnings") or []
    return {
        "queries_generated": int(gdelt.get("queries_generated") or 0),
        "gdelt_enabled": bool(gdelt.get("enabled")),
        "gdelt_articles_fetched": int(gdelt.get("articles_fetched") or 0),
        "gdelt_events_extracted": int(gdelt.get("events_extracted") or 0),
        "gdelt_rate_limited": bool(gdelt.get("rate_limited")),
        "gdelt_connector_errors": gdelt_errors,
        "gdelt_warnings": gdelt_warnings,
        "rss_enabled": bool(rss.get("enabled")),
        "rss_feeds_checked": int(rss.get("feeds_checked") or 0),
        "rss_items_fetched": int(rss.get("rss_items_fetched") or 0),
        "rss_items_matched": int(rss.get("rss_items_matched") or 0),
        "rss_events_extracted": int(rss.get("events_extracted") or 0),
        "rss_connector_errors": rss_errors,
        "rss_warnings": rss_warnings,
        "weather_enabled": bool(weather.get("enabled")),
        "weather_locations_checked": int(weather.get("locations_checked") or 0),
        "weather_events_extracted": int(weather.get("weather_events_extracted") or 0),
        "weather_connector_errors": weather_errors,
        "weather_warnings": weather_warnings,
        "connector_errors": gdelt_errors + rss_errors + weather_errors,
        "warnings": gdelt_warnings + rss_warnings + weather_warnings,
    }


def _mode_warnings(mode: str, connector_results: list[dict]) -> list[str]:
    warnings: list[str] = []
    for result in connector_results:
        warnings.extend(result.get("warnings") or [])
    if mode == "REAL":
        enabled = [
            result for result in connector_results
            if result.get("connector") in {"gdelt_event_connector", "real_search_event_connector", "open_meteo_weather_connector"} and result.get("enabled")
        ]
        if not enabled:
            warnings.append("REAL_MODE_NO_CONNECTORS_ENABLED")
    return list(dict.fromkeys(warnings))
