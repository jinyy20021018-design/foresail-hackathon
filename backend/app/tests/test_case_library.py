import os
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import reset_store
from app.services.document_service import reset_document_store


class CaseLibraryTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ["USE_LLM_SUMMARY"] = "false"
        os.environ["REQUIRE_LLM_AGENT"] = "false"
        os.environ["OPENAI_API_KEY"] = ""
        reset_store()
        reset_document_store()
        self.client = TestClient(app)

    def approve_all_fields(self, case_id: str) -> None:
        fields = self.client.get(f"/api/cases/{case_id}/extracted-fields").json()
        self.assertTrue(fields)
        for field in fields:
            response = self.client.post(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/approve")
            self.assertEqual(response.status_code, 200, response.text)

    def test_list_cases_empty(self) -> None:
        response = self.client.get("/api/cases")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"cases": []})

    def test_clean_demo_case_appears_in_case_library(self) -> None:
        created = self.client.post("/api/cases/demo/clean")
        self.assertEqual(created.status_code, 200, created.text)

        response = self.client.get("/api/cases")
        self.assertEqual(response.status_code, 200, response.text)
        cases = response.json()["cases"]
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["case_id"], created.json()["case_id"])
        self.assertEqual(cases[0]["vessel"], "CAPEMOLLINI")
        self.assertEqual(cases[0]["open_actions_count"], 0)

    def test_conflict_demo_case_reports_high_conflict_and_high_risk(self) -> None:
        created = self.client.post("/api/cases/demo/conflict")
        self.assertEqual(created.status_code, 200, created.text)

        summary = self.client.get("/api/cases").json()["cases"][0]
        self.assertEqual(summary["case_id"], created.json()["case_id"])
        self.assertGreater(summary["high_conflicts_count"], 0)
        self.assertEqual(summary["risk_level"], "High")

    def test_next_deadline_uses_confirmed_facts_before_agent_run(self) -> None:
        case_id = self.client.post("/api/cases/demo/clean").json()["case_id"]
        self.approve_all_fields(case_id)
        confirm = self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.assertEqual(confirm.status_code, 200, confirm.text)

        summary = self.client.get("/api/cases").json()["cases"][0]
        self.assertEqual(summary["next_deadline"], {"label": "Latest shipment", "date": "2026-11-30"})

    def test_agent_run_updates_case_library_counts_and_latest_run(self) -> None:
        case_id = self.client.post("/api/cases/demo/clean").json()["case_id"]
        self.approve_all_fields(case_id)
        self.client.post(f"/api/cases/{case_id}/confirm-fields")

        run = self.client.post(f"/api/cases/{case_id}/agent-run")
        self.assertEqual(run.status_code, 200, run.text)

        summary = self.client.get("/api/cases").json()["cases"][0]
        self.assertEqual(summary["status"], "AT_RISK")
        self.assertEqual(summary["risk_level"], "High")
        self.assertEqual(summary["last_agent_run_id"], run.json()["agent_run_id"])
        self.assertTrue(summary["last_agent_run_at"])
        self.assertGreater(summary["information_gaps_count"], 0)
        self.assertEqual(summary["open_actions_count"], 0)
        self.assertEqual(summary["next_deadline"]["label"], "Latest Shipment Date")


if __name__ == "__main__":
    unittest.main()
