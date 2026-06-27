import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import get_watch_profile, reset_store
from app.services.document_service import reset_document_store
from app.services.event_deduplicator import deduplicate_events
from app.services.event_ingestion_service import fetch_events_for_case, list_external_events_for_run
from app.services.event_normalizer import normalize_event


class ExternalEventIngestionTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ["WEATHER_API_ENABLED"] = "false"
        os.environ["NEWS_API_ENABLED"] = "false"
        os.environ["GDELT_ENABLED"] = "false"
        os.environ["OPEN_METEO_ENABLED"] = "false"
        os.environ["REAL_SEARCH_ENABLED"] = "false"
        os.environ["REAL_SEARCH_FEED_URLS"] = ""
        os.environ["USE_LLM_EVENT_EXTRACTION"] = "false"
        reset_store()
        reset_document_store()
        self.client = TestClient(app)

    def create_confirmed_case(self) -> str:
        case_id = self.client.post("/api/cases/demo/clean").json()["case_id"]
        fields = self.client.get(f"/api/cases/{case_id}/extracted-fields").json()
        for field in fields:
            response = self.client.post(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/approve")
            self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.assertEqual(response.status_code, 200, response.text)
        return case_id

    def test_mock_mode_only_calls_mock_connector(self) -> None:
        case_id = self.create_confirmed_case()
        result = fetch_events_for_case(case_id, get_watch_profile(case_id))
        self.assertEqual(result["mode"], "MOCK")
        self.assertEqual(result["connectors_called"], ["mock_event_connector"])
        self.assertGreater(result["events_deduped_count"], 0)

    def test_real_mode_does_not_call_mock_connector(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "REAL"
        case_id = self.create_confirmed_case()
        result = fetch_events_for_case(case_id, get_watch_profile(case_id))
        self.assertEqual(result["connectors_called"], ["gdelt_event_connector", "open_meteo_weather_connector"])
        self.assertEqual(result["events_deduped_count"], 0)

    def test_hybrid_mode_calls_mock_and_real_connectors(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "HYBRID"
        case_id = self.create_confirmed_case()
        result = fetch_events_for_case(case_id, get_watch_profile(case_id))
        self.assertEqual(result["connectors_called"], ["mock_event_connector", "gdelt_event_connector", "open_meteo_weather_connector"])
        self.assertGreater(result["events_deduped_count"], 0)

    def test_disabled_real_connectors_return_empty_without_error(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "REAL"
        case_id = self.create_confirmed_case()
        result = fetch_events_for_case(case_id, get_watch_profile(case_id))
        self.assertEqual(result["connector_errors"], [])
        self.assertEqual(result["events_raw_count"], 0)
        self.assertIn("REAL_MODE_NO_CONNECTORS_ENABLED", result["warnings"])

    def test_connector_failure_does_not_fail_ingestion(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "REAL"
        case_id = self.create_confirmed_case()
        with patch("app.services.event_connectors.gdelt_event_connector.GdeltEventConnector.fetch_events", side_effect=RuntimeError("gdelt down")):
            result = fetch_events_for_case(case_id, get_watch_profile(case_id))
        self.assertEqual(result["mode"], "REAL")
        self.assertEqual(result["connector_errors"][0]["connector"], "gdelt_event_connector")

    def test_event_normalizer_outputs_complete_fields(self) -> None:
        event = normalize_event(
            {
                "title": "Severe weather risk near Chittagong",
                "source": "weather_connector",
                "source_type": "WEATHER",
                "event_type": "WEATHER",
                "affected_ports": ["Chittagong"],
                "severity": "HIGH",
                "confidence": 1.5,
            },
            "CASE-001",
        )
        for field in ["event_id", "case_id", "source", "source_type", "event_type", "title", "affected_ports", "severity", "confidence", "dedup_key"]:
            self.assertIn(field, event)
        self.assertEqual(event["confidence"], 1.0)
        self.assertEqual(event["type"], "WEATHER")

    def test_deduplicator_removes_duplicate_events(self) -> None:
        first = {"event_id": "A", "dedup_key": "K", "source_type": "MOCK", "confidence": 0.5}
        second = {"event_id": "B", "dedup_key": "K", "source_type": "NEWS", "confidence": 0.4}
        deduped, stats = deduplicate_events([first, second])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(stats["duplicates_removed"], 1)
        self.assertEqual(deduped[0]["event_id"], "B")

    def test_fetch_api_requires_confirmed_facts(self) -> None:
        case_id = self.client.post("/api/cases", json={"case_name": "Blank"}).json()["case_id"]
        response = self.client.post(f"/api/cases/{case_id}/external-events/fetch")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["error"], "WATCH_PROFILE_REQUIRED")

    def test_agent_run_trace_contains_ingestion_steps_and_persists_events(self) -> None:
        case_id = self.create_confirmed_case()
        response = self.client.post(f"/api/cases/{case_id}/agent-run")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        names = {step["name"] for step in payload["trace"]}
        self.assertIn("Fetch External Events", names)
        self.assertIn("Normalize Events", names)
        self.assertIn("Deduplicate Events", names)
        events = list_external_events_for_run(case_id, payload["agent_run_id"])
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0]["case_id"], case_id)
        self.assertEqual(events[0]["agent_run_id"], payload["agent_run_id"])

    def test_relevance_engine_handles_normalized_event(self) -> None:
        case_id = self.create_confirmed_case()
        event = normalize_event(
            {
                "event_id": "REAL-001",
                "source": "weather_connector",
                "source_type": "WEATHER",
                "event_type": "WEATHER",
                "title": "Severe weather near Shanghai",
                "event_time": "2026-11-24",
                "affected_ports": ["Shanghai"],
                "affected_region": "East China Sea",
                "severity": "HIGH",
                "confidence": 0.9,
                "impact": "Potential departure delay near Shanghai route",
            },
            case_id,
        )
        from app.services.document_service import get_confirmed_facts
        from app.services.relevance_engine import classify_event

        result = classify_event(get_confirmed_facts(case_id), event)
        self.assertIn(result["classification"], {"Relevant", "Watch"})
        self.assertEqual(result["source_type"], "WEATHER")


if __name__ == "__main__":
    unittest.main()
