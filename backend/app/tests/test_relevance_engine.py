import unittest

from app.services.case_service import create_demo_case, reset_store
from app.services.mock_event_service import get_mock_events
from app.services.relevance_engine import classify_event, classify_events


class RelevanceEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case()
        self.events = get_mock_events()
        self.results = {result["event_id"]: result for result in classify_events(self.case, self.events)}

    def test_weather_at_loading_port_inside_shipment_window_escalates_to_relevant(self) -> None:
        in_window = self.case["etd"]  # ETD sits inside the shipment window
        event = {
            "event_id": "EVT-WX-001",
            "title": "Severe weather near Shanghai",
            "type": "WEATHER",
            "event_time": in_window,
            "affected_ports": ["Shanghai"],
            "affected_region": "Shanghai",
            "severity": "HIGH",
            "impact": "Potential departure delay near Shanghai route",
        }
        result = classify_event(self.case, event)
        self.assertEqual(result["classification"], "Relevant")
        self.assertGreaterEqual(result["score"], 70)
        self.assertIn("watched_port_match", result["matched_factors"])
        self.assertNotIn("weather_watch_cap", result["matched_factors"])

    def test_weather_off_route_window_is_still_capped(self) -> None:
        event = {
            "event_id": "EVT-WX-002",
            "title": "Storm system over East China Sea",
            "type": "WEATHER",
            "event_time": "2026-10-01",
            "affected_ports": [],
            "affected_region": "East China Sea",
            "severity": "HIGH",
            "impact": "General maritime weather advisory",
        }
        result = classify_event(self.case, event)
        self.assertIn("weather_watch_cap", result["matched_factors"])
        self.assertLessEqual(result["score"], 60)

    def test_expected_classifications(self) -> None:
        expectations = {
            "EVT-001": "Relevant",
            "EVT-002": "Relevant",
            "EVT-003": "Relevant",
            "EVT-004": "Irrelevant",
            "EVT-005": "Irrelevant",
        }
        for event_id, expected in expectations.items():
            self.assertEqual(self.results[event_id]["classification"], expected)

    def test_score_thresholds(self) -> None:
        self.assertGreaterEqual(self.results["EVT-001"]["score"], 70)
        self.assertGreaterEqual(self.results["EVT-002"]["score"], 70)
        self.assertGreaterEqual(self.results["EVT-003"]["score"], 70)
        self.assertLess(self.results["EVT-004"]["score"], 35)
        self.assertLess(self.results["EVT-005"]["score"], 35)

    def test_results_carry_incoterm_attribution(self) -> None:
        attribution = self.results["EVT-003"]["attribution"]
        self.assertEqual(attribution["incoterm"], "CIF")
        self.assertIn("PORT_OF_LOADING", attribution["legs_hit"])
        self.assertTrue(attribution["our_payment_risk"])
        self.assertTrue(attribution["monitor_worthy"])

    def test_irrelevant_events_do_not_show_misleading_positive_factors(self) -> None:
        for event_id in ["EVT-004", "EVT-005"]:
            factors = set(self.results[event_id]["matched_factors"])
            self.assertNotIn("shipment_window_overlap", factors)
            self.assertNotIn("high_severity", factors)
            self.assertIn("Filtered out because", self.results[event_id]["explanation"])


if __name__ == "__main__":
    unittest.main()
