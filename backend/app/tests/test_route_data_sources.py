import unittest

from app.services.port_registry_service import resolve_port
from app.services.route_geometry_service import build_route_geometry


class ExtendedPortRegistryTest(unittest.TestCase):
    def test_curated_ports_still_resolve_first(self) -> None:
        record = resolve_port("Shanghai")
        self.assertEqual(record["unlocode"], "CNSHA")
        self.assertEqual(record["region"], "East China Sea")

    def test_extended_port_resolves_by_name(self) -> None:
        record = resolve_port("Valparaiso")
        self.assertIsNotNone(record)
        self.assertTrue(str(record["unlocode"]).startswith("CL"))

    def test_extended_port_resolves_with_country_suffix(self) -> None:
        record = resolve_port("Ajman, United Arab Emirates")
        self.assertIsNotNone(record)
        self.assertEqual(record["unlocode"], "AEAJM")

    def test_unknown_port_returns_none(self) -> None:
        self.assertIsNone(resolve_port("Totally Fictional Harbor 42"))


class SearouteGeometryTest(unittest.TestCase):
    def test_stored_route_still_preferred(self) -> None:
        geometry = build_route_geometry("Shanghai", "Chittagong")
        self.assertEqual(geometry["source"], "lane_network")

    def test_unstored_pair_uses_searoute(self) -> None:
        geometry = build_route_geometry("Xiamen", "Colombo")
        self.assertEqual(geometry["source"], "searoute_marnet")
        self.assertEqual(geometry["confidence"], "high")
        self.assertGreater(len(geometry["coordinates"]), 10)
        self.assertGreater(geometry["distance_nautical_miles"], 1000)
        first = geometry["coordinates"][0]
        self.assertAlmostEqual(first[0], 24.48, delta=1.5)

    def test_extended_ports_get_real_route(self) -> None:
        geometry = build_route_geometry("Ningbo", "Valparaiso")
        self.assertEqual(geometry["source"], "searoute_marnet")
        self.assertGreater(len(geometry["coordinates"]), 10)


if __name__ == "__main__":
    unittest.main()
