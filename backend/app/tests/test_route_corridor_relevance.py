import unittest

from app.services.relevance_engine import classify_event


class RouteCorridorRelevanceTest(unittest.TestCase):
    def test_hormuz_security_event_on_shanghai_dubai_route_is_not_irrelevant(self) -> None:
        case = {
            "case_id": "CASE-TEST",
            "vessel": "GULF HORIZON",
            "port_of_loading": "Shanghai, China",
            "port_of_discharge": "Jebel Ali, United Arab Emirates",
            "final_destination": "Dubai, United Arab Emirates",
            "route": "Shanghai -> South China Sea -> Strait of Malacca -> Indian Ocean -> Strait of Hormuz -> Jebel Ali",
            "etd": "2026-06-28",
            "eta": "2026-07-18",
        }
        event = {
            "event_id": "EVT-HORMUZ",
            "title": "Traffic Through Strait of Hormuz Slows After Attack on Ship",
            "type": "SECURITY",
            "event_time": "2026-06-27",
            "affected_ports": [],
            "affected_region": "",
            "severity": "HIGH",
            "impact": "Route disruption near Hormuz",
        }

        result = classify_event(case, event)

        self.assertNotEqual(result["classification"], "Irrelevant")
        self.assertIn("route_corridor_text_match", result["matched_factors"])
        self.assertGreaterEqual(result["score"], 35)


if __name__ == "__main__":
    unittest.main()
