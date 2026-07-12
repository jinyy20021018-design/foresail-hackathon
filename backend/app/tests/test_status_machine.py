import os
import unittest

from app.services.case_service import create_demo_case, continue_monitoring, get_case, get_timeline, reset_store
from app.services.monitoring_service import run_monitoring_cycle


class StatusMachineTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        reset_store()
        self.case = create_demo_case()

    def test_relevant_event_moves_case_to_at_risk_until_llm_actions_exist(self) -> None:
        result = run_monitoring_cycle(self.case["case_id"])
        self.assertEqual(result["case"]["status"], "AT_RISK")

        statuses = [entry["status"] for entry in get_timeline(self.case["case_id"])]
        self.assertEqual(statuses, ["DRAFT", "ACTIVE", "WATCHING", "AT_RISK"])

    def test_continue_monitoring_requires_confirmed_actions_and_plans(self) -> None:
        run_monitoring_cycle(self.case["case_id"])
        with self.assertRaises(ValueError):
            continue_monitoring(self.case["case_id"])


if __name__ == "__main__":
    unittest.main()
