import os
import unittest

from app.agents.monitoring_agent import MonitoringAgent
from app.api.monitoring import run_agent_monitoring_cycle
from app.services.agent_summary_service import generate_agent_summary
from app.services.case_service import continue_monitoring, create_demo_case, get_case, reset_store


class MonitoringAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ["USE_LLM_SUMMARY"] = "false"
        os.environ["REQUIRE_LLM_AGENT"] = "false"
        os.environ["OPENAI_API_KEY"] = ""
        reset_store()
        self.case = create_demo_case()
        self.agent = MonitoringAgent()

    def test_agent_orchestrator_runs_full_cycle(self) -> None:
        result = self.agent.run_monitoring_cycle(self.case["case_id"])

        self.assertEqual(result["case_id"], "CASE-001")
        self.assertEqual(result["status_before"], "ACTIVE")
        self.assertEqual(result["status_after"], "ACTION_REQUIRED")
        self.assertEqual(result["events_scanned"], 5)
        self.assertEqual(result["relevant_count"], 2)
        self.assertEqual(result["watch_count"], 1)
        self.assertEqual(result["irrelevant_count"], 2)
        self.assertEqual(result["case"]["status"], "ACTION_REQUIRED")

    def test_agent_result_contains_summary_and_trace(self) -> None:
        result = self.agent.run_monitoring_cycle(self.case["case_id"])

        self.assertIn("Agent scanned 5 external events", result["summary"])
        self.assertGreaterEqual(len(result["trace"]), 8)
        self.assertEqual(result["trace"][0]["name"], "Load Case")
        self.assertEqual(result["trace"][-1]["name"], "Generate Agent Summary")

    def test_agent_run_endpoint_returns_expected_fields(self) -> None:
        result = run_agent_monitoring_cycle(self.case["case_id"])
        expected_fields = {
            "agent_run_id",
            "case_id",
            "status_before",
            "status_after",
            "summary",
            "summary_source",
            "llm_enabled",
            "llm_required",
            "trace",
            "events_scanned",
            "relevant_count",
            "watch_count",
            "irrelevant_count",
            "case",
            "watch_profile",
            "relevance_results",
            "risk_summary",
            "obligations",
            "information_gaps",
            "action_drafts",
            "actions",
            "status_timeline",
        }

        self.assertTrue(expected_fields.issubset(result.keys()))

    def test_summary_fallback_without_llm_api_key(self) -> None:
        os.environ["USE_LLM_SUMMARY"] = "true"
        os.environ.pop("OPENAI_API_KEY", None)
        try:
            summary = generate_agent_summary(
                case=self.case,
                status_before="ACTIVE",
                status_after="ACTION_REQUIRED",
                relevance_results=[
                    {"classification": "Relevant"},
                    {"classification": "Watch"},
                    {"classification": "Irrelevant"},
                ],
                risk_summary={
                    "trigger_events": ["EVT-001"],
                    "watch_events_considered": ["EVT-003"],
                    "exposures": [{"category": "Shipping"}],
                },
                actions=[{"action_id": "ACT-001"}],
            )
        finally:
            os.environ.pop("USE_LLM_SUMMARY", None)

        self.assertIn("Agent scanned 3 external events", summary)
        self.assertIn("Trigger events: EVT-001", summary)

    def test_required_llm_without_api_key_raises(self) -> None:
        os.environ["REQUIRE_LLM_AGENT"] = "true"
        os.environ["OPENAI_API_KEY"] = ""
        try:
            with self.assertRaises(RuntimeError):
                self.agent.run_monitoring_cycle(self.case["case_id"])
        finally:
            os.environ.pop("REQUIRE_LLM_AGENT", None)

    def test_continue_monitoring_after_agent_run(self) -> None:
        self.agent.run_monitoring_cycle(self.case["case_id"])
        continue_monitoring(self.case["case_id"])
        self.assertEqual(get_case(self.case["case_id"])["status"], "MONITORING")


if __name__ == "__main__":
    unittest.main()
