import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import reset_store
from app.services.document_service import reset_document_store


class LLMActionPlanFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["USE_LLM_SUMMARY"] = "false"
        os.environ["REQUIRE_LLM_AGENT"] = "false"
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        reset_store()
        reset_document_store()
        self.client = TestClient(app)

    def confirmed_analyzed_case(self) -> str:
        case_id = self.client.post("/api/cases/demo/clean").json()["case_id"]
        for field in self.client.get(f"/api/cases/{case_id}/extracted-fields").json():
            self.assertEqual(self.client.post(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/approve").status_code, 200)
        self.assertEqual(self.client.post(f"/api/cases/{case_id}/confirm-fields").status_code, 200)
        self.assertEqual(self.client.post(f"/api/cases/{case_id}/agent-run").status_code, 200)
        return case_id

    def action_output(self, case_id: str) -> dict:
        risk = self.client.get(f"/api/cases/{case_id}/risk-summary").json()
        obligations = self.client.get(f"/api/cases/{case_id}/obligations").json()
        hazards = self.client.get(f"/api/cases/{case_id}/hazards").json()
        return {
            "actions": [{
                "title": "Confirm latest ETA with carrier",
                "owner_role": "Logistics",
                "priority": "High",
                "deadline": "Today",
                "deadline_date": "2026-07-13",
                "rationale": "Current shipping disruption requires an updated operational fact.",
                "related_exposure": risk["exposures"][0]["category"] if risk["exposures"] else "",
                "responsible_party": "SELLER",
                "linked_hazard_ids": [hazards[0]["hazard_id"]] if hazards else [],
                "linked_obligation_ids": [obligations[0]["obligation_id"]] if obligations else [],
            }]
        }

    def plan_output(self, action_id: str) -> dict:
        plans = []
        for index, plan_type in enumerate(["LOW_COST", "BALANCED", "MAX_PROTECTION"]):
            plans.append({
                "plan_type": plan_type,
                "plan_name": f"{plan_type.title()} Treatment Plan",
                "summary": "A complete treatment alternative based on confirmed actions.",
                "recommended": index == 1,
                "recommendation_level": "Recommended" if index == 1 else "Alternative",
                "estimated_cost_level": ["Low", "Medium", "High"][index],
                "estimated_cost_amount": [500, 5000, 15000][index],
                "estimated_cost_currency": "USD",
                "estimated_time_to_execute": "1 business day",
                "approval_required": index > 0,
                "approval_roles": [] if index == 0 else ["Business Owner"],
                "covered_risks": ["Shipment delay risk"],
                "residual_risks": [{
                    "risk_title": "ETA may change again",
                    "description": "Carrier estimates can change.",
                    "severity": "Medium",
                    "reason_not_fully_covered": "External operations remain outside direct control.",
                    "monitoring_trigger": "ETA changes by two days.",
                    "owner_role": "Logistics",
                }],
                "required_actions": ["Confirm latest ETA with carrier"],
                "linked_action_ids": [action_id],
                "linked_gap_ids": [],
                "linked_obligation_ids": [],
                "assumptions": ["Carrier can provide an update."],
                "preconditions": ["The action set remains current."],
                "recheck_triggers": ["A new hazard is detected."],
                "rationale": "This option matches the confirmed action and risk context.",
            })
        return {"plans": plans}

    def create_confirmed_action_set(self, case_id: str) -> dict:
        with patch("app.services.action_set_service.generate_structured", return_value=self.action_output(case_id)):
            response = self.client.post(f"/api/cases/{case_id}/action-sets/generate")
        self.assertEqual(response.status_code, 200, response.text)
        action_set = response.json()
        confirmed = self.client.post(f"/api/cases/{case_id}/action-sets/{action_set['action_set_id']}/confirm")
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        return confirmed.json()

    def test_action_set_can_be_edited_confirmed_and_becomes_immutable(self) -> None:
        case_id = self.confirmed_analyzed_case()
        with patch("app.services.action_set_service.generate_structured", return_value=self.action_output(case_id)):
            action_set = self.client.post(f"/api/cases/{case_id}/action-sets/generate").json()
        action = {**action_set["actions"][0], "owner_role": "Trade Operations", "selected": True}
        updated = self.client.put(f"/api/cases/{case_id}/action-sets/{action_set['action_set_id']}", json={"actions": [action]})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["actions"][0]["owner_role"], "Trade Operations")
        confirmed = self.client.post(f"/api/cases/{case_id}/action-sets/{action_set['action_set_id']}/confirm")
        self.assertEqual(confirmed.json()["status"], "CONFIRMED")
        immutable = self.client.put(f"/api/cases/{case_id}/action-sets/{action_set['action_set_id']}", json={"actions": [action]})
        self.assertEqual(immutable.status_code, 409)
        self.assertEqual(immutable.json()["error"], "ACTION_SET_IMMUTABLE")

    def test_empty_selection_cannot_be_confirmed(self) -> None:
        case_id = self.confirmed_analyzed_case()
        with patch("app.services.action_set_service.generate_structured", return_value=self.action_output(case_id)):
            action_set = self.client.post(f"/api/cases/{case_id}/action-sets/generate").json()
        action = {**action_set["actions"][0], "selected": False}
        self.client.put(f"/api/cases/{case_id}/action-sets/{action_set['action_set_id']}", json={"actions": [action]})
        response = self.client.post(f"/api/cases/{case_id}/action-sets/{action_set['action_set_id']}/confirm")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "NO_ACTIONS_SELECTED")

    def test_llm_failure_does_not_create_action_set(self) -> None:
        case_id = self.confirmed_analyzed_case()
        os.environ["OPENAI_API_KEY"] = ""
        response = self.client.post(f"/api/cases/{case_id}/action-sets/generate")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get(f"/api/cases/{case_id}/action-sets").json(), [])

    def test_plan_generation_requires_confirmed_actions(self) -> None:
        case_id = self.confirmed_analyzed_case()
        response = self.client.post(f"/api/cases/{case_id}/treatment-plans/generate", json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "ACTIONS_NOT_CONFIRMED")

    def test_three_llm_plans_are_versioned_and_idempotent(self) -> None:
        case_id = self.confirmed_analyzed_case()
        action_set = self.create_confirmed_action_set(case_id)
        action_id = action_set["actions"][0]["action_id"]
        with patch("app.services.treatment_plan_service.generate_structured", return_value=self.plan_output(action_id)) as llm:
            first = self.client.post(f"/api/cases/{case_id}/treatment-plans/generate", json={"action_set_id": action_set["action_set_id"]})
            second = self.client.post(f"/api/cases/{case_id}/treatment-plans/generate", json={"action_set_id": action_set["action_set_id"]})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["plan_set_id"], second.json()["plan_set_id"])
        self.assertEqual(len(first.json()["plans"]), 3)
        self.assertEqual(sum(1 for item in first.json()["plans"] if item["status"] == "RECOMMENDED"), 1)
        self.assertEqual(llm.call_count, 1)

    def test_new_action_version_preserves_plan_history(self) -> None:
        case_id = self.confirmed_analyzed_case()
        action_set = self.create_confirmed_action_set(case_id)
        action_id = action_set["actions"][0]["action_id"]
        with patch("app.services.treatment_plan_service.generate_structured", return_value=self.plan_output(action_id)):
            self.client.post(f"/api/cases/{case_id}/treatment-plans/generate", json={"action_set_id": action_set["action_set_id"]})
        cloned = self.client.post(f"/api/cases/{case_id}/action-sets/{action_set['action_set_id']}/clone").json()
        self.assertEqual(cloned["version"], 2)
        self.assertEqual(len(self.client.get(f"/api/cases/{case_id}/plan-sets").json()), 1)

    def test_approval_package_is_bound_to_plan_and_action_versions(self) -> None:
        case_id = self.confirmed_analyzed_case()
        action_set = self.create_confirmed_action_set(case_id)
        with patch("app.services.treatment_plan_service.generate_structured", return_value=self.plan_output(action_set["actions"][0]["action_id"])):
            result = self.client.post(f"/api/cases/{case_id}/treatment-plans/generate", json={"action_set_id": action_set["action_set_id"]}).json()
        package = self.client.post(f"/api/cases/{case_id}/treatment-plans/{result['recommended_plan_id']}/approval-package")
        self.assertEqual(package.status_code, 200, package.text)
        self.assertEqual(package.json()["plan_set_id"], result["plan_set_id"])
        self.assertEqual(package.json()["action_set_id"], action_set["action_set_id"])

    def test_continue_monitoring_requires_latest_plan_set(self) -> None:
        case_id = self.confirmed_analyzed_case()
        blocked = self.client.post(f"/api/cases/{case_id}/continue-monitoring")
        self.assertEqual(blocked.status_code, 409)
        action_set = self.create_confirmed_action_set(case_id)
        with patch("app.services.treatment_plan_service.generate_structured", return_value=self.plan_output(action_set["actions"][0]["action_id"])):
            self.client.post(f"/api/cases/{case_id}/treatment-plans/generate", json={"action_set_id": action_set["action_set_id"]})
        continued = self.client.post(f"/api/cases/{case_id}/continue-monitoring")
        self.assertEqual(continued.status_code, 200, continued.text)
        self.assertEqual(continued.json()["case"]["status"], "MONITORING")


if __name__ == "__main__":
    unittest.main()
