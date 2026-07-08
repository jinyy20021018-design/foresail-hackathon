import unittest

from app.services.case_service import create_demo_case, reset_store
from app.services.route_map_service import build_route_map


class RouteMapServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()

    def test_route_map_for_demo_case(self) -> None:
        case = create_demo_case()
        payload = build_route_map(case["case_id"])
        self.assertEqual(payload["case_id"], case["case_id"])
        self.assertEqual(payload["geometry"]["source"], "lane_network")
        self.assertGreater(len(payload["geometry"]["coordinates"]), 10)
        self.assertIn("neutral_message", payload["threat_summary"])

    def test_route_map_unknown_case(self) -> None:
        with self.assertRaises(KeyError):
            build_route_map("CASE-404")


if __name__ == "__main__":
    unittest.main()
