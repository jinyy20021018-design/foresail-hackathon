import os
import unittest
from unittest.mock import patch

from app.services.llm_relevance_factor_service import build_factor_metadata


class LlmRelevanceFactorTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["USE_LLM_RELEVANCE_FACTORS"] = "false"
        self.case = {
            "case_id": "CASE-001",
            "vessel": "CAPEMOLLINI",
            "route": "Shanghai -> Chittagong -> Dhaka",
            "port_of_loading": "Shanghai",
            "port_of_discharge": "Chittagong",
            "final_destination": "Dhaka",
            "etd": "2026-11-25",
            "eta": "2026-12-08",
            "latest_shipment_date": "2026-11-30",
            "payment_method": "LC at sight",
            "incoterm": "CIF",
        }
        self.event = {
            "event_id": "EVT-001",
            "title": "Chittagong port disruption",
            "event_type": "PORT_DISRUPTION",
            "affected_ports": ["Chittagong"],
            "severity": "HIGH",
            "confidence": 0.9,
        }

    def tearDown(self) -> None:
        os.environ.pop("USE_LLM_RELEVANCE_FACTORS", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_disabled_mode_uses_deterministic_candidate_metadata(self) -> None:
        metadata = build_factor_metadata(self.case, self.event, ["watched_port_match", "high_severity"])

        self.assertFalse(metadata["llm_factor_used"])
        self.assertEqual([item["factor"] for item in metadata["llm_candidate_factors"]], ["watched_port_match", "high_severity"])
        self.assertEqual([item["factor"] for item in metadata["validated_factors"]], ["watched_port_match", "high_severity"])
        self.assertEqual(metadata["rejected_factors"], [])

    def test_llm_candidates_are_validated_against_deterministic_factors(self) -> None:
        os.environ["USE_LLM_RELEVANCE_FACTORS"] = "true"
        os.environ["OPENAI_API_KEY"] = "test-key"
        llm_payload = {
            "candidate_factors": [
                {"factor": "watched_port_match", "evidence": "The article mentions Chittagong port.", "confidence": 0.88},
                {"factor": "vessel_match", "evidence": "The article mentions a vessel.", "confidence": 0.72},
                {"factor": "not_allowed", "evidence": "Bad factor.", "confidence": 0.5},
            ],
            "missing_direct_evidence": ["No confirmed ETA delay"],
            "llm_summary": "Port match is plausible, but vessel evidence is not supported.",
        }
        with patch("app.services.llm_relevance_factor_service._extract_candidate_factors", return_value=llm_payload):
            metadata = build_factor_metadata(self.case, self.event, ["watched_port_match", "high_severity"])

        self.assertTrue(metadata["llm_factor_used"])
        self.assertIn("watched_port_match", [item["factor"] for item in metadata["validated_factors"]])
        rejected = {item["factor"]: item["reason"] for item in metadata["rejected_factors"]}
        self.assertEqual(rejected["vessel_match"], "Not supported by deterministic case/event validation.")
        self.assertEqual(rejected["not_allowed"], "Unknown factor.")
        self.assertEqual(metadata["missing_direct_evidence"], ["No confirmed ETA delay"])

    def test_llm_failure_falls_back_to_deterministic_metadata(self) -> None:
        os.environ["USE_LLM_RELEVANCE_FACTORS"] = "true"
        os.environ["OPENAI_API_KEY"] = "test-key"
        with patch("app.services.llm_relevance_factor_service._extract_candidate_factors", side_effect=TimeoutError()):
            metadata = build_factor_metadata(self.case, self.event, ["watched_port_match"])

        self.assertFalse(metadata["llm_factor_used"])
        self.assertEqual([item["factor"] for item in metadata["validated_factors"]], ["watched_port_match"])
        self.assertEqual(metadata["llm_factor_error"], "TimeoutError")


if __name__ == "__main__":
    unittest.main()
