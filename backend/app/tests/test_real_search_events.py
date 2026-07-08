import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import get_watch_profile, reset_store
from app.services.document_service import reset_document_store
from app.services.news_event_extractor import extract_event_from_news_item
from app.services.rss_search_service import filter_rss_items, fetch_rss_items
from app.services.search_query_builder import build_external_event_queries


class RealSearchEventsTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ["REAL_SEARCH_ENABLED"] = "false"
        os.environ["REAL_SEARCH_FEED_URLS"] = ""
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

    def test_query_builder_generates_vessel_port_route_queries(self) -> None:
        case_id = self.create_confirmed_case()
        queries = build_external_event_queries(case_id, get_watch_profile(case_id))
        texts = " ".join(query["query_text"] for query in queries)
        self.assertIn("CAPEMOLLINI", texts)
        self.assertIn("Chittagong", texts)
        self.assertTrue(any(query["query_type"] == "VESSEL" for query in queries))
        self.assertTrue(any(query["query_type"] == "PORT" for query in queries))

    def test_external_event_queries_requires_confirmed_facts(self) -> None:
        case_id = self.client.post("/api/cases", json={"case_name": "Blank"}).json()["case_id"]
        response = self.client.get(f"/api/cases/{case_id}/external-event-queries")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "WATCH_PROFILE_REQUIRED")

    def test_rss_filter_matches_port_and_disruption_keywords(self) -> None:
        case_id = self.create_confirmed_case()
        watch_profile = get_watch_profile(case_id)
        items = [{
            "title": "Chittagong port strike causes shipping disruption",
            "summary": "Backlog reported at Bangladesh terminals.",
            "published_at": "2026-11-26T00:00:00+00:00",
            "link": "https://example.com/chittagong-strike",
            "source_feed": "test",
            "raw_payload": {},
        }]
        queries = build_external_event_queries(case_id, watch_profile)
        matched = filter_rss_items(items, queries, watch_profile, 5)
        self.assertEqual(len(matched), 1)
        self.assertIn("chittagong", [term.lower() for term in matched[0]["matched_terms"]])

    def test_news_event_extractor_event_types_and_confidence(self) -> None:
        case_id = self.create_confirmed_case()
        watch_profile = get_watch_profile(case_id)
        matched = {
            "rss_item": {
                "title": "Chittagong port strike causes severe disruption",
                "summary": "The port strike has delayed vessel schedules.",
                "published_at": "2026-11-26T00:00:00+00:00",
                "link": "https://example.com/strike",
                "raw_payload": {},
            },
            "matched_query_ids": ["Q-001"],
            "matched_terms": ["Chittagong", "strike"],
            "match_score": 0.8,
        }
        event = extract_event_from_news_item(matched, watch_profile)
        self.assertEqual(event["event_type"], "PORT_DISRUPTION")
        self.assertEqual(event["severity"], "HIGH")
        self.assertLessEqual(event["confidence"], 1.0)

        weather = dict(matched)
        weather["rss_item"] = {**matched["rss_item"], "title": "Bay of Bengal typhoon warning", "summary": "Storm and wind warnings affect shipping."}
        self.assertEqual(extract_event_from_news_item(weather, watch_profile)["event_type"], "WEATHER")

        policy = dict(matched)
        policy["rss_item"] = {**matched["rss_item"], "title": "Bangladesh customs import restriction", "summary": "New customs disruption reported."}
        self.assertEqual(extract_event_from_news_item(policy, watch_profile)["event_type"], "TRADE_POLICY")

    def test_real_search_disabled_returns_warning(self) -> None:
        case_id = self.create_confirmed_case()
        response = self.client.post(f"/api/cases/{case_id}/external-events/search")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload.get("rss_items_fetched", 0), 0)
        self.assertEqual(payload.get("rss_items_matched", 0), 0)
        self.assertIn("Real search connector disabled.", payload["warnings"])

    def test_rss_feed_file_search_extracts_and_persists_event(self) -> None:
        case_id = self.create_confirmed_case()
        feed = """<?xml version="1.0"?><rss><channel><item><title>Chittagong port congestion disrupts vessels</title><description>Shipping delay at Chittagong port.</description><link>https://example.com/rss-event</link><pubDate>Thu, 26 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as file:
            file.write(feed)
            feed_url = "file:///" + file.name.replace("\\", "/")
        os.environ["REAL_SEARCH_ENABLED"] = "true"
        os.environ["REAL_SEARCH_FEED_URLS"] = feed_url
        items, errors = fetch_rss_items([feed_url], 5)
        self.assertFalse(errors)
        self.assertEqual(len(items), 1)
        response = self.client.post(f"/api/cases/{case_id}/external-events/search")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["rss_items_fetched"], 1)
        self.assertGreaterEqual(payload["events_extracted_count"], 1)
        stored = self.client.get(f"/api/cases/{case_id}/external-events").json()
        self.assertTrue(any(event.get("url") == "https://example.com/rss-event" for event in stored))

    def test_hybrid_agent_trace_includes_real_search_steps(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "HYBRID"
        os.environ["REAL_SEARCH_ENABLED"] = "false"
        case_id = self.create_confirmed_case()
        response = self.client.post(f"/api/cases/{case_id}/agent-run")
        self.assertEqual(response.status_code, 200, response.text)
        names = {step["name"] for step in response.json()["trace"]}
        self.assertIn("Build Search Queries", names)
        self.assertIn("Fetch GDELT Events", names)
        self.assertIn("Fetch Open-Meteo Weather", names)
        self.assertIn("Extract Real Events", names)


if __name__ == "__main__":
    unittest.main()
