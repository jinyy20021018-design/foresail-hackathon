import os
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import clear_runtime_case_cache, reset_store
from app.services.document_service import clear_runtime_document_cache, reset_document_store


class MVP21WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["USE_LLM_SUMMARY"] = "false"
        os.environ["REQUIRE_LLM_AGENT"] = "false"
        os.environ["OPENAI_API_KEY"] = ""
        os.environ.pop("USE_LLM_EXTRACTION", None)
        os.environ.pop("LLM_EXTRACTION_TEST_INVALID_JSON", None)
        reset_store()
        reset_document_store()
        self.client = TestClient(app)

    def create_clean_case(self) -> str:
        response = self.client.post("/api/cases/demo/clean")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["case_id"]

    def create_conflict_case(self) -> str:
        response = self.client.post("/api/cases/demo/conflict")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["case_id"]

    def approve_all_fields(self, case_id: str) -> None:
        fields = self.client.get(f"/api/cases/{case_id}/extracted-fields").json()
        self.assertTrue(fields)
        for field in fields:
            response = self.client.post(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/approve")
            self.assertEqual(response.status_code, 200, response.text)

    def test_clean_demo_persists_case_documents_fields_and_confirmed_facts(self) -> None:
        case_id = self.create_clean_case()
        self.approve_all_fields(case_id)
        confirm = self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.assertEqual(confirm.status_code, 200, confirm.text)

        clear_runtime_case_cache()
        clear_runtime_document_cache()

        case = self.client.get(f"/api/cases/{case_id}")
        documents = self.client.get(f"/api/cases/{case_id}/documents")
        fields = self.client.get(f"/api/cases/{case_id}/extracted-fields")
        facts = self.client.get(f"/api/cases/{case_id}/confirmed-facts")

        self.assertEqual(case.status_code, 200, case.text)
        self.assertEqual(documents.status_code, 200, documents.text)
        self.assertEqual(fields.status_code, 200, fields.text)
        self.assertEqual(facts.status_code, 200, facts.text)
        self.assertEqual(case.json()["vessel"], "CAPEMOLLINI")
        self.assertEqual(len(documents.json()), 3)
        self.assertGreater(len(fields.json()), 10)
        self.assertEqual(facts.json()["amount"], 1250000)

    def test_field_evidence_endpoint_returns_source_context(self) -> None:
        case_id = self.create_clean_case()
        field = self.client.get(f"/api/cases/{case_id}/extracted-fields").json()[0]
        response = self.client.get(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/evidence")
        self.assertEqual(response.status_code, 200, response.text)
        evidence = response.json()
        self.assertEqual(evidence["field_name"], field["field_name"])
        self.assertIn("evidence_text", evidence)
        self.assertIn("source_document_name", evidence)

    def test_high_field_conflict_blocks_confirmation_until_resolved(self) -> None:
        case_id = self.create_conflict_case()
        self.approve_all_fields(case_id)

        conflicts = self.client.get(f"/api/cases/{case_id}/field-conflicts")
        self.assertEqual(conflicts.status_code, 200, conflicts.text)
        high_conflict = next(conflict for conflict in conflicts.json() if conflict["field_name"] == "amount")
        self.assertEqual(high_conflict["severity"], "High")
        self.assertEqual(high_conflict["status"], "OPEN")

        blocked = self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.assertEqual(blocked.status_code, 400)

        resolved = self.client.post(
            f"/api/cases/{case_id}/field-conflicts/{high_conflict['conflict_id']}/resolve",
            json={"resolved_value": 1250000, "resolution_note": "Use contract amount", "resolved_by": "tester"},
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["status"], "RESOLVED")

        confirmed = self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.assertEqual(confirmed.status_code, 200, confirmed.text)

    def test_workflow_state_reports_conflict_blocker(self) -> None:
        case_id = self.create_conflict_case()
        workflow = self.client.get(f"/api/cases/{case_id}/workflow-state")
        self.assertEqual(workflow.status_code, 200, workflow.text)
        steps = {step["name"]: step["status"] for step in workflow.json()["steps"]}
        self.assertEqual(steps["Resolve Conflicts"], "BLOCKED")
        self.assertEqual(steps["Confirm Case Facts"], "BLOCKED")

    def test_agent_run_history_and_trace_are_saved(self) -> None:
        case_id = self.create_clean_case()
        self.approve_all_fields(case_id)
        self.client.post(f"/api/cases/{case_id}/confirm-fields")

        run = self.client.post(f"/api/cases/{case_id}/agent-run")
        self.assertEqual(run.status_code, 200, run.text)
        run_id = run.json()["agent_run_id"]

        runs = self.client.get(f"/api/cases/{case_id}/agent-runs")
        detail = self.client.get(f"/api/cases/{case_id}/agent-runs/{run_id}")
        trace = self.client.get(f"/api/cases/{case_id}/agent-runs/{run_id}/trace")

        self.assertEqual(runs.status_code, 200, runs.text)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(trace.status_code, 200, trace.text)
        self.assertEqual(runs.json()[0]["agent_run_id"], run_id)
        self.assertEqual(detail.json()["run_status"], "COMPLETED")
        self.assertGreaterEqual(len(trace.json()), 12)

    def test_agent_run_no_longer_generates_action_drafts(self) -> None:
        case_id = self.create_clean_case()
        self.approve_all_fields(case_id)
        self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.client.post(f"/api/cases/{case_id}/agent-run")

        drafts = self.client.get(f"/api/cases/{case_id}/action-drafts").json()
        self.assertEqual(drafts, [])


if __name__ == "__main__":
    unittest.main()
