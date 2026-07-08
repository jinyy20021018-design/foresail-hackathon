import unittest

from app.services.route_geometry_service import build_route_geometry


class RouteGeometryTests(unittest.TestCase):
    def test_shanghai_chittagong_uses_lane_network(self) -> None:
        geometry = build_route_geometry("Shanghai", "Chittagong")
        self.assertEqual(geometry["source"], "lane_network")
        self.assertGreater(len(geometry["coordinates"]), 10)
        self.assertGreater(geometry["distance_nautical_miles"], 3000)

    def test_shanghai_jebel_ali_uses_lane_network(self) -> None:
        geometry = build_route_geometry(
            "Shanghai, China",
            "Jebel Ali, United Arab Emirates",
            "Dubai, United Arab Emirates",
        )
        self.assertEqual(geometry["source"], "lane_network")
        self.assertGreater(len(geometry["coordinates"]), 20)
        self.assertGreater(geometry["distance_nautical_miles"], 5000)
        self.assertEqual(geometry["origin"]["display_name"], "Shanghai")
        self.assertEqual(geometry["destination"]["display_name"], "Dubai")

    def test_heuristic_route_has_multiple_points(self) -> None:
        geometry = build_route_geometry("Shenzhen", "Surabaya")
        self.assertIn(geometry["source"], {"lane_network", "heuristic_lane"})
        self.assertGreater(len(geometry["coordinates"]), 2)

    def test_inland_leg_appended_for_dhaka(self) -> None:
        geometry = build_route_geometry("Shanghai", "Chittagong", "Dhaka")
        self.assertEqual(len(geometry["legs"]), 2)
        self.assertEqual(geometry["legs"][1]["type"], "inland")

    def test_unresolved_ports_return_warnings(self) -> None:
        geometry = build_route_geometry("Unknown A", "Unknown B")
        self.assertEqual(geometry["source"], "unresolved")
        self.assertTrue(geometry["warnings"])


if __name__ == "__main__":
    unittest.main()
