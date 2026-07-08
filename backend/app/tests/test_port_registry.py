import unittest

from app.services.port_registry_service import resolve_port, resolve_region_coordinates


class PortRegistryTests(unittest.TestCase):
    def test_shanghai_alias(self) -> None:
        record = resolve_port("Shanghai")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["unlocode"], "CNSHA")
        self.assertAlmostEqual(record["lat"], 31.2304, places=3)

    def test_chattogram_alias(self) -> None:
        record = resolve_port("Chattogram")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["unlocode"], "BDCGP")

    def test_long_beach_alias(self) -> None:
        record = resolve_port("Long Beach")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["unlocode"], "USLAX")

    def test_unknown_port(self) -> None:
        self.assertIsNone(resolve_port("Unknown Port XYZ"))

    def test_region_coordinates(self) -> None:
        coordinates = resolve_region_coordinates("Bay of Bengal")
        self.assertIsNotNone(coordinates)
        assert coordinates is not None
        self.assertAlmostEqual(coordinates[0], 15.0, places=1)


if __name__ == "__main__":
    unittest.main()
