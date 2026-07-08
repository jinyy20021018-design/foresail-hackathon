import os
import unittest

from app.agents.monitoring_agent import MonitoringAgent
from app.services.case_service import create_demo_case, reset_store
from app.services.route_map_service import build_route_map


class RouteMapEventsTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ["USE_LLM_SUMMARY"] = "false"
        os.environ["REQUIRE_LLM_AGENT"] = "false"
        os.environ["OPENAI_API_KEY"] = ""
        reset_store()

    def test_route_map_includes_relevant_events_after_agent_run(self) -> None:
        case = create_demo_case()
        case_id = case["case_id"]

        MonitoringAgent().run_monitoring_cycle(case_id)
        payload = build_route_map(case_id)
        self.assertTrue(payload["threat_summary"]["has_route_threats"])
        self.assertGreater(len(payload["map_events"]), 0)
        self.assertIsNotNone(payload["threat_summary"]["primary_threat"])


if __name__ == "__main__":
    unittest.main()
