import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import get_watch_profile, reset_store
from app.services.document_service import reset_document_store
from app.services.event_connectors.gdelt_event_connector import GdeltEventConnector
from app.services.event_connectors.open_meteo_weather_connector import OpenMeteoWeatherConnector
from app.services.event_ingestion_service import fetch_events_for_case
from app.services.news_event_extractor import extract_event_from_gdelt_article
from app.services.port_geo_service import resolve_location_coordinates
from app.services.search_query_builder import build_external_event_queries


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class RealApiEventConnectorTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ["GDELT_ENABLED"] = "false"
        os.environ["OPEN_METEO_ENABLED"] = "false"
        os.environ["USE_LLM_EVENT_EXTRACTION"] = "false"
        reset_store()
        reset_document_store()
        self.client = TestClient(app)

    def create_confirmed_case(self) -> str:
        case_id = self.client.post("/api/cases/demo/clean").json()["case_id"]
        for field in self.client.get(f"/api/cases/{case_id}/extracted-fields").json():
            self.client.post(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/approve")
        response = self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.assertEqual(response.status_code, 200, response.text)
        return case_id

    def test_query_builder_generates_real_api_queries(self) -> None:
        case_id = self.create_confirmed_case()
        queries = build_external_event_queries(case_id, get_watch_profile(case_id))
        self.assertTrue(any(query["query_type"] == "VESSEL" and query["source_hint"] == "GDELT" for query in queries))
        self.assertTrue(any(query["query_type"] == "PORT" and query["source_hint"] == "GDELT" for query in queries))
        self.assertTrue(any(query["query_type"] == "WEATHER_REGION" and query["source_hint"] == "OPEN_METEO" for query in queries))

    def test_external_event_queries_requires_confirmed_facts(self) -> None:
        case_id = self.client.post("/api/cases", json={"case_name": "Blank"}).json()["case_id"]
        response = self.client.get(f"/api/cases/{case_id}/external-event-queries")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "WATCH_PROFILE_REQUIRED")

    def test_disabled_connectors_return_empty_with_warnings(self) -> None:
        case_id = self.create_confirmed_case()
        profile = get_watch_profile(case_id)
        gdelt = GdeltEventConnector()
        meteo = OpenMeteoWeatherConnector()
        self.assertEqual(gdelt.fetch_events(profile, case_id), [])
        self.assertIn("GDELT connector disabled.", gdelt.last_result["warnings"])
        self.assertEqual(meteo.fetch_events(profile, case_id), [])
        self.assertIn("Open-Meteo connector disabled.", meteo.last_result["warnings"])

    def test_gdelt_article_event_type_rules(self) -> None:
        profile = {"watched_vessel": "CAPEMOLLINI", "watched_ports": ["Shanghai", "Chittagong", "Dhaka"], "watched_route_regions": ["Bay of Bengal"]}
        query = {"query_id": "Q-001", "query_text": "Chittagong port strike congestion", "query_type": "PORT", "priority": "HIGH"}
        event = extract_event_from_gdelt_article({"title": "Chittagong port strike disrupts cargo", "url": "https://example.com/a", "seendate": "20260115100000Z"}, query, profile)
        self.assertEqual(event["event_type"], "PORT_DISRUPTION")
        self.assertLessEqual(event["confidence"], 1.0)
        policy = extract_event_from_gdelt_article({"title": "Bangladesh customs import restriction", "url": "https://example.com/b"}, query, profile)
        self.assertEqual(policy["event_type"], "TRADE_POLICY")
        vessel = extract_event_from_gdelt_article({"title": "CAPEMOLLINI vessel delay ETA update", "url": "https://example.com/c"}, query, profile)
        self.assertEqual(vessel["event_type"], "VESSEL_DELAY")

    def test_gdelt_connector_converts_mocked_api_article(self) -> None:
        os.environ["GDELT_ENABLED"] = "true"
        case_id = self.create_confirmed_case()
        payload = {"articles": [{"title": "Chittagong port congestion disrupts cargo", "url": "https://example.com/gdelt", "seendate": "20260115100000Z"}]}
        with patch("app.services.event_connectors.gdelt_event_connector.urllib.request.urlopen", return_value=_FakeResponse(payload)):
            events = GdeltEventConnector().fetch_events(get_watch_profile(case_id), case_id)
        self.assertTrue(events)
        self.assertEqual(events[0]["source"], "gdelt_event_connector")
        self.assertEqual(events[0]["event_type"], "PORT_DISRUPTION")

    def test_open_meteo_high_wind_and_precipitation_events(self) -> None:
        os.environ["OPEN_METEO_ENABLED"] = "true"
        case_id = self.create_confirmed_case()
        forecast = {"hourly": {"time": ["2026-01-16T12:00", "2026-01-16T13:00"], "precipitation": [0, 25], "wind_gusts_10m": [65, 10], "weather_code": [0, 80]}}
        with patch("app.services.event_connectors.open_meteo_weather_connector.urllib.request.urlopen", return_value=_FakeResponse(forecast)):
            events = OpenMeteoWeatherConnector().fetch_events(get_watch_profile(case_id), case_id)
        self.assertTrue(any(event["severity"] == "HIGH" and event["event_type"] == "WEATHER" for event in events))

    def test_location_not_found_warns_without_exception(self) -> None:
        self.assertIsNone(resolve_location_coordinates("Unknown Port"))
        os.environ["OPEN_METEO_ENABLED"] = "true"
        connector = OpenMeteoWeatherConnector()
        events = connector.fetch_events({"watched_ports": ["Unknown Port"], "watched_route_regions": []}, "CASE-001")
        self.assertEqual(events, [])
        self.assertTrue(any("LOCATION_COORDINATES_NOT_FOUND" in warning for warning in connector.last_result["warnings"]))

    def test_hybrid_ingestion_includes_mock_gdelt_and_open_meteo(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "HYBRID"
        os.environ["GDELT_ENABLED"] = "true"
        os.environ["OPEN_METEO_ENABLED"] = "true"
        case_id = self.create_confirmed_case()
        gdelt_payload = {"articles": [{"title": "Chittagong port strike disrupts cargo", "url": "https://example.com/hybrid", "seendate": "20260115100000Z"}]}
        meteo_payload = {"hourly": {"time": ["2026-01-16T12:00"], "precipitation": [0], "wind_gusts_10m": [65], "weather_code": [0]}}
        with patch("app.services.event_connectors.gdelt_event_connector.urllib.request.urlopen", return_value=_FakeResponse(gdelt_payload)), patch("app.services.event_connectors.open_meteo_weather_connector.urllib.request.urlopen", return_value=_FakeResponse(meteo_payload)):
            result = fetch_events_for_case(case_id, get_watch_profile(case_id))
        self.assertEqual(result["mode"], "HYBRID")
        self.assertIn("mock_event_connector", result["connectors_called"])
        self.assertIn("gdelt_event_connector", result["connectors_called"])
        self.assertIn("open_meteo_weather_connector", result["connectors_called"])
        self.assertGreaterEqual(result["events_deduped_count"], 3)

    def test_agent_trace_contains_real_api_steps(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "REAL"
        os.environ["GDELT_ENABLED"] = "false"
        os.environ["OPEN_METEO_ENABLED"] = "false"
        case_id = self.create_confirmed_case()
        response = self.client.post(f"/api/cases/{case_id}/agent-run")
        self.assertEqual(response.status_code, 200, response.text)
        names = {step["name"] for step in response.json()["trace"]}
        self.assertIn("Build Search Queries", names)
        self.assertIn("Fetch GDELT Events", names)
        self.assertIn("Fetch Open-Meteo Weather", names)


if __name__ == "__main__":
    unittest.main()
