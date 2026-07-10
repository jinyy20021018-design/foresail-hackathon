import os


class PolicyRegistryConnector:
    name = "policy_registry_connector"

    def __init__(self) -> None:
        self.last_result: dict = {}

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        if os.getenv("POLICY_REGISTRY_ENABLED", "true").lower() != "true":
            self.last_result = {"enabled": False, "policy_events_extracted": 0, "warnings": ["Policy registry connector disabled."]}
            return []

        from app.services.case_service import get_case
        from app.services.policy_registry_service import match_policies_for_case
        from app.services.voyage_schedule_service import build_voyage_schedule

        try:
            case = get_case(case_id)
        except KeyError:
            self.last_result = {"enabled": True, "policy_events_extracted": 0, "warnings": [f"Case not found: {case_id}"]}
            return []

        matches = match_policies_for_case(case, build_voyage_schedule(case))
        events = matches["pending_policy_events"]
        self.last_result = {
            "enabled": True,
            "policy_events_extracted": len(events),
            "active_policies_matched": len(matches["active_policies"]),
            "warnings": [],
            "connector_errors": [],
        }
        return events
