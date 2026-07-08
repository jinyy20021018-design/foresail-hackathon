import unittest

from app.services.case_service import create_demo_case, reset_store
from app.services.mock_event_service import get_mock_events
from app.services.relevance_engine import classify_events


class RelevanceEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case()
        self.events = get_mock_events()
        self.results = {result["event_id"]: result for result in classify_events(self.case, self.events)}

    def test_weather_at_watched_port_without_route_region_is_watch(self) -> None:
        event = {
            "event_id": "EVT-WX-001",
            "title": "Severe weather near Shanghai",
            "type": "WEATHER",
            "event_time": "2026-11-24",
            "affected_ports": ["Shanghai"],
            "affected_region": "Shanghai",
            "severity": "HIGH",
            "impact": "Potential departure delay near Shanghai route",
        }
        from app.services.relevance_engine import classify_event

        result = classify_event(self.case, event)
        self.assertEqual(result["classification"], "Watch")
        self.assertGreaterEqual(result["score"], 35)
        self.assertIn("watched_port_match", result["matched_factors"])
        self.assertNotIn("unrelated_region", result["matched_factors"])

    def test_expected_classifications(self) -> None:
        expectations = {
            "EVT-001": "Relevant",
            "EVT-002": "Relevant",
            "EVT-003": "Watch",
            "EVT-004": "Irrelevant",
            "EVT-005": "Irrelevant",
        }
        for event_id, expected in expectations.items():
            self.assertEqual(self.results[event_id]["classification"], expected)

    def test_score_thresholds(self) -> None:
        self.assertGreaterEqual(self.results["EVT-001"]["score"], 70)
        self.assertGreaterEqual(self.results["EVT-002"]["score"], 70)
        self.assertGreaterEqual(self.results["EVT-003"]["score"], 35)
        self.assertLess(self.results["EVT-003"]["score"], 70)
        self.assertLess(self.results["EVT-004"]["score"], 35)
        self.assertLess(self.results["EVT-005"]["score"], 35)

    def test_irrelevant_events_do_not_show_misleading_positive_factors(self) -> None:
        for event_id in ["EVT-004", "EVT-005"]:
            factors = set(self.results[event_id]["matched_factors"])
            self.assertNotIn("shipment_window_overlap", factors)
            self.assertNotIn("high_severity", factors)
            self.assertIn("Filtered out because", self.results[event_id]["explanation"])


if __name__ == "__main__":
    unittest.main()
