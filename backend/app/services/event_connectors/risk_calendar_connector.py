import os


class RiskCalendarConnector:
    name = "risk_calendar_connector"

    def __init__(self) -> None:
        self.last_result: dict = {}

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        if os.getenv("RISK_CALENDAR_ENABLED", "true").lower() != "true":
            self.last_result = {"enabled": False, "calendar_events_extracted": 0, "warnings": ["Risk calendar connector disabled."]}
            return []

        from app.services.case_service import get_case
        from app.services.risk_calendar_service import calendar_events_for_case
        from app.services.voyage_schedule_service import build_voyage_schedule

        try:
            case = get_case(case_id)
        except KeyError:
            self.last_result = {"enabled": True, "calendar_events_extracted": 0, "warnings": [f"Case not found: {case_id}"]}
            return []

        events = calendar_events_for_case(case, build_voyage_schedule(case))
        self.last_result = {"enabled": True, "calendar_events_extracted": len(events), "warnings": [], "connector_errors": []}
        return events
