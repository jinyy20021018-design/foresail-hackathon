import os
import unittest
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import create_demo_case, reset_store
from app.services.document_service import get_field_conflicts, reset_document_store
from app.services.extraction_schema_validator import validate_extracted_fields


class DocumentWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["USE_LLM_SUMMARY"] = "false"
        os.environ["REQUIRE_LLM_AGENT"] = "false"
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ.pop("USE_LLM_EXTRACTION", None)
        os.environ.pop("LLM_EXTRACTION_TEST_INVALID_JSON", None)
        reset_store()
        reset_document_store()
        self.case = create_demo_case()
        self.client = TestClient(app)

    def upload_text(self, filename: str, document_type: str, text: str) -> dict:
        response = self.client.post(
            f"/api/cases/{self.case['case_id']}/documents/upload",
            data={"document_type": document_type},
            files={"file": (filename, BytesIO(text.encode("utf-8")), "text/plain")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def seed_documents(self) -> None:
        self.upload_text(
            "contract.txt",
            "CONTRACT_PO",
            "\n".join([
                "Commodity: Cotton Yarn",
                "Quantity: 100 MT",
                "Amount: USD 1250000",
                "Currency: USD",
                "Buyer: Demo Buyer",
                "Seller: Demo Seller",
                "Incoterm: CIF",
                "Payment Method: LC at sight",
                "Final Destination: Dhaka",
            ]),
        )
        self.upload_text(
            "booking.txt",
            "BOOKING_CONFIRMATION",
            "\n".join([
                "Booking Reference: BKG-7788",
                "Vessel: CAPEMOLLINI",
                "Route: Shanghai -> Chittagong -> Dhaka",
                "Port of Loading: Shanghai",
                "Port of Discharge: Chittagong",
                "Final Destination: Dhaka",
                "ETD: 2026-11-25",
                "ETA: 2026-12-08",
            ]),
        )
        self.upload_text(
            "lc.txt",
            "LETTER_OF_CREDIT",
            "\n".join([
                "LC Number: LC-001",
                "Issuing Bank: Demo Bank",
                "Applicant: Demo Buyer",
                "Beneficiary: Demo Seller",
                "Amount: USD 1250000",
                "Currency: USD",
                "Latest Shipment: 2026-11-30",
                "LC Expiry: 2026-12-31",
                "Presentation Period: 21",
                "Payment Method: LC at sight",
            ]),
        )

    def extract(self) -> list[dict]:
        response = self.client.post(f"/api/cases/{self.case['case_id']}/documents/extract")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["extracted_fields"]

    def approve_all_fields(self, fields: list[dict]) -> None:
        for field in fields:
            response = self.client.post(f"/api/cases/{self.case['case_id']}/extracted-fields/{field['field_id']}/approve")
            self.assertEqual(response.status_code, 200, response.text)

    def test_document_upload_endpoint_works(self) -> None:
        document = self.upload_text("contract.txt", "CONTRACT_PO", "Incoterm: CIF")
        self.assertEqual(document["parse_status"], "UPLOADED")

    def test_extraction_returns_fields_with_evidence_and_confidence(self) -> None:
        self.seed_documents()
        fields = self.extract()
        self.assertTrue(fields)
        self.assertTrue(all("evidence_text" in field for field in fields))
        self.assertTrue(all("confidence" in field for field in fields))

    def test_contract_quantity_is_split_from_amount(self) -> None:
        self.upload_text(
            "contract.txt",
            "CONTRACT_PO",
            "\n".join([
                "Commodity: Granular Urea Fertilizer",
                "Quantity: 5000 metric tons",
                "Currency: USD",
                "Buyer: Bangladesh Agro Trading Ltd.",
                "Seller: Shanghai AgriChem Export Co., Ltd.",
                "Incoterm: CIF",
                "Payment Method: LC at sight",
                "Final Destination: Dhaka",
            ]),
        )
        values = {field["field_name"]: field["value"] for field in self.extract()}
        self.assertEqual(values["quantity"], 5000)
        self.assertEqual(values["quantity_unit"], "metric tons")
        self.assertNotIn("amount", values)

    def test_contract_amount_and_quantity_are_both_extracted(self) -> None:
        self.upload_text(
            "contract.txt",
            "CONTRACT_PO",
            "\n".join([
                "Commodity: Granular Urea Fertilizer",
                "Quantity: 5000 metric tons",
                "Amount: USD 1,250,000",
                "Currency: USD",
                "Buyer: Bangladesh Agro Trading Ltd.",
                "Seller: Shanghai AgriChem Export Co., Ltd.",
                "Incoterm: CIF",
                "Payment Method: LC at sight",
                "Final Destination: Dhaka",
            ]),
        )
        values = {field["field_name"]: field["value"] for field in self.extract()}
        self.assertEqual(values["quantity"], 5000)
        self.assertEqual(values["quantity_unit"], "metric tons")
        self.assertEqual(values["amount"], 1250000)
        self.assertEqual(values["currency"], "USD")

    def test_llm_validator_splits_quantity_unit_and_rejects_non_money_amount(self) -> None:
        validated, warnings = validate_extracted_fields(
            [
                {"field_name": "quantity", "value": "5000 metric tons", "evidence_text": "Quantity: 5000 metric tons", "confidence": 0.9},
                {"field_name": "amount", "value": "5000 metric tons", "evidence_text": "Quantity: 5000 metric tons", "confidence": 0.9},
                {"field_name": "amount", "value": "USD 1,250,000", "evidence_text": "Amount: USD 1,250,000", "confidence": 0.9},
            ],
            {"filename": "contract.txt"},
        )
        values = {field["field_name"]: field["value"] for field in validated}
        self.assertEqual(values["quantity"], 5000)
        self.assertEqual(values["quantity_unit"], "metric tons")
        self.assertEqual(values["amount"], 1250000)
        self.assertTrue(any("Skipped non-money amount value" in warning for warning in warnings))

    def test_approve_edit_reject_field_works(self) -> None:
        self.seed_documents()
        fields = self.extract()
        field_id = fields[0]["field_id"]
        self.assertEqual(self.client.post(f"/api/cases/{self.case['case_id']}/extracted-fields/{field_id}/approve").status_code, 200)
        edit = self.client.post(
            f"/api/cases/{self.case['case_id']}/extracted-fields/{field_id}/edit",
            json={"value": "Edited Value"},
        )
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(edit.json()["review_status"], "EDITED")
        reject = self.client.post(f"/api/cases/{self.case['case_id']}/extracted-fields/{field_id}/reject")
        self.assertEqual(reject.status_code, 200)
        self.assertEqual(reject.json()["review_status"], "REJECTED")

    def test_confirm_fields_generates_confirmed_facts(self) -> None:
        self.seed_documents()
        fields = self.extract()
        self.approve_all_fields(fields)
        response = self.client.post(f"/api/cases/{self.case['case_id']}/confirm-fields")
        self.assertEqual(response.status_code, 200, response.text)
        facts = response.json()
        self.assertEqual(facts["vessel"], "CAPEMOLLINI")
        self.assertEqual(facts["currency"], "USD")

    def test_missing_critical_fields_block_confirmation(self) -> None:
        self.seed_documents()
        fields = self.extract()
        for field in fields:
            if field["field_name"] != "vessel":
                self.client.post(f"/api/cases/{self.case['case_id']}/extracted-fields/{field['field_id']}/approve")
        response = self.client.post(f"/api/cases/{self.case['case_id']}/confirm-fields")
        self.assertEqual(response.status_code, 400)

    def test_agent_run_returns_obligations_and_gaps_without_drafts(self) -> None:
        self.seed_documents()
        fields = self.extract()
        self.approve_all_fields(fields)
        self.client.post(f"/api/cases/{self.case['case_id']}/confirm-fields")
        response = self.client.post(f"/api/cases/{self.case['case_id']}/agent-run")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertGreaterEqual(len(result["trace"]), 12)
        self.assertTrue(result["obligations"])
        self.assertTrue(result["information_gaps"])
        self.assertEqual(result["action_drafts"], [])
        obligation_names = {obligation["name"] for obligation in result["obligations"]}
        self.assertIn("Latest Shipment Date", obligation_names)
        latest = next(obligation for obligation in result["obligations"] if obligation["name"] == "Latest Shipment Date")
        self.assertIn("At risk", latest["current_assessment"])
        self.assertEqual(latest["severity"], "High")

    def test_no_llm_api_key_extraction_fallback_works(self) -> None:
        os.environ["USE_LLM_EXTRACTION"] = "true"
        os.environ["OPENAI_API_KEY"] = ""
        self.seed_documents()
        fields = self.extract()
        self.assertTrue(fields)

    def test_invalid_llm_json_fallback_works(self) -> None:
        os.environ["USE_LLM_EXTRACTION"] = "true"
        os.environ["LLM_EXTRACTION_TEST_INVALID_JSON"] = "true"
        self.seed_documents()
        fields = self.extract()
        self.assertTrue(fields)

    def test_document_extraction_does_not_add_mock_event_eta_conflict(self) -> None:
        self.upload_text(
            "booking.txt",
            "BOOKING_CONFIRMATION",
            "\n".join([
                "Booking Reference: BKG-7788",
                "Vessel: CAPEMOLLINI",
                "Route: Shanghai -> Chittagong -> Dhaka",
                "Port of Loading: Shanghai",
                "Port of Discharge: Chittagong",
                "Final Destination: Dhaka",
                "ETD: 2026-11-25",
                "ETA: 2026-12-08",
            ]),
        )
        fields = self.extract()
        self.assertTrue(any(field["field_name"] == "eta" for field in fields))
        conflicts = get_field_conflicts(self.case["case_id"])
        self.assertFalse(any(
            value["source_document_name"] == "mock_event_feed"
            for conflict in conflicts
            for value in conflict["values"]
        ))


if __name__ == "__main__":
    unittest.main()
