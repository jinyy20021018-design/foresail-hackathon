from app.services.case_service import get_case, get_timeline, get_watch_profile, set_monitoring_outputs
from app.services.event_ingestion_service import fetch_events_for_case
from app.services.relevance_engine import classify_events
from app.services.risk_mapper import summarize_exposures


def run_monitoring_cycle(case_id: str) -> dict:
    case = get_case(case_id)
    events = fetch_events_for_case(case_id, get_watch_profile(case_id), persist=True)["events"]
    relevance_results = classify_events(case, events)
    risk_summary = summarize_exposures(case, events, relevance_results)
    actions = []
    set_monitoring_outputs(case_id, relevance_results, risk_summary, actions)

    return {
        "case": get_case(case_id),
        "events": events,
        "relevance_results": relevance_results,
        "risk_summary": risk_summary,
        "actions": actions,
        "status_timeline": get_timeline(case_id),
    }
