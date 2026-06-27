import os
import unittest

from app.services.case_service import create_demo_case, continue_monitoring, get_case, get_timeline, reset_store
from app.services.monitoring_service import run_monitoring_cycle


class StatusMachineTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        reset_store()
        self.case = create_demo_case()

    def test_relevant_event_moves_case_to_action_required(self) -> None:
        result = run_monitoring_cycle(self.case["case_id"])
        self.assertEqual(result["case"]["status"], "ACTION_REQUIRED")

        statuses = [entry["status"] for entry in get_timeline(self.case["case_id"])]
        self.assertEqual(statuses, ["DRAFT", "ACTIVE", "WATCHING", "AT_RISK", "ACTION_REQUIRED"])

    def test_continue_monitoring_moves_case_to_monitoring(self) -> None:
        run_monitoring_cycle(self.case["case_id"])
        continue_monitoring(self.case["case_id"])
        self.assertEqual(get_case(self.case["case_id"])["status"], "MONITORING")


if __name__ == "__main__":
    unittest.main()
