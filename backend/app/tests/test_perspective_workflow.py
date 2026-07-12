import os
import unittest
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import reset_store
from app.services.document_service import reset_document_store


class PerspectiveWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["USE_LLM_SUMMARY"] = "false"
        os.environ["REQUIRE_LLM_AGENT"] = "false"
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ.pop("USE_LLM_EXTRACTION", None)
        reset_store()
        reset_document_store()
        self.client = TestClient(app)

    def create_clean_demo(self) -> str:
        response = self.client.post("/api/cases/demo/clean")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["case_id"]

    def extract(self, case_id: str) -> list[dict]:
        response = self.client.post(f"/api/cases/{case_id}/documents/extract")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["extracted_fields"]

    def approve_all(self, case_id: str, fields: list[dict]) -> None:
        for field in fields:
            response = self.client.post(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/approve")
            self.assertEqual(response.status_code, 200, response.text)

    def confirm(self, case_id: str) -> dict:
        response = self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def perspective_field(self, fields: list[dict]) -> dict:
        matches = [field for field in fields if field["field_name"] == "trade_perspective"]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_extraction_emits_pending_perspective_field_with_evidence(self) -> None:
        case_id = self.create_clean_demo()
        field = self.perspective_field(self.extract(case_id))
        self.assertEqual(field["value"], "SELLER")
        self.assertEqual(field["review_status"], "PENDING")
        self.assertTrue(field["requires_confirmation"])
        self.assertEqual(field["detection_source"], "AUTO_DETECTED")
        self.assertEqual(field["detection_basis"], "LC Beneficiary · Shanghai Solaris PV Co., Ltd")
        self.assertIn("Shanghai Solaris", field["evidence_text"])

    def test_confirm_applies_detected_perspective_to_case(self) -> None:
        case_id = self.create_clean_demo()
        fields = self.extract(case_id)
        self.approve_all(case_id, fields)
        confirmed = self.confirm(case_id)
        self.assertEqual(confirmed["trade_perspective"], "SELLER")
        self.assertEqual(confirmed["perspective_source"], "AUTO_DETECTED")
        self.assertEqual(confirmed["perspective_basis"], "LC Beneficiary · Shanghai Solaris PV Co., Ltd")
        case = self.client.get(f"/api/cases/{case_id}").json()
        self.assertEqual(case["trade_perspective"], "SELLER")
        self.assertEqual(case["perspective_source"], "AUTO_DETECTED")
        self.assertEqual(case["perspective_basis"], "LC Beneficiary · Shanghai Solaris PV Co., Ltd")

    def test_edited_perspective_confirms_as_manual(self) -> None:
        case_id = self.create_clean_demo()
        fields = self.extract(case_id)
        field = self.perspective_field(fields)
        response = self.client.post(
            f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/edit",
            json={"value": "BUYER"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.approve_all(case_id, [f for f in fields if f["field_id"] != field["field_id"]])
        confirmed = self.confirm(case_id)
        self.assertEqual(confirmed["trade_perspective"], "BUYER")
        self.assertEqual(confirmed["perspective_source"], "MANUAL")
        case = self.client.get(f"/api/cases/{case_id}").json()
        self.assertEqual(case["trade_perspective"], "BUYER")

    def test_put_perspective_after_confirm_syncs_confirmed_facts(self) -> None:
        case_id = self.create_clean_demo()
        fields = self.extract(case_id)
        self.approve_all(case_id, fields)
        self.confirm(case_id)
        response = self.client.put(f"/api/cases/{case_id}/perspective", json={"trade_perspective": "BUYER"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["trade_perspective"], "BUYER")
        self.assertEqual(response.json()["perspective_source"], "MANUAL")
        facts = self.client.get(f"/api/cases/{case_id}/confirmed-facts").json()
        self.assertEqual(facts["trade_perspective"], "BUYER")
        self.assertEqual(facts["perspective_source"], "MANUAL")

    def test_buyer_demo_detects_buyer_seat_from_lc_applicant(self) -> None:
        response = self.client.post("/api/cases/demo/buyer")
        self.assertEqual(response.status_code, 200, response.text)
        case_id = response.json()["case_id"]
        self.assertEqual(response.json()["incoterm"], "FOB")
        fields = self.extract(case_id)
        values = {field["field_name"]: field["value"] for field in fields}
        self.assertEqual(values["incoterm"], "FOB")
        self.assertEqual(values["incoterm_named_place"], "Chittagong")
        self.assertEqual(values["shipper"], "Chittagong Alloy Works Ltd")
        self.assertEqual(values["consignee"], "Shanghai Solaris PV Co., Ltd")
        field = self.perspective_field(fields)
        self.assertEqual(field["value"], "BUYER")
        self.assertEqual(field["detection_source"], "AUTO_DETECTED")
        self.assertEqual(field["detection_basis"], "LC Applicant · Shanghai Solaris PV Co., Ltd")
        self.approve_all(case_id, fields)
        confirmed = self.confirm(case_id)
        self.assertEqual(confirmed["trade_perspective"], "BUYER")
        self.assertEqual(confirmed["perspective_source"], "AUTO_DETECTED")

    def test_no_profile_match_defaults_without_blocking_confirm(self) -> None:
        response = self.client.post("/api/cases/demo")
        self.assertEqual(response.status_code, 200, response.text)
        case_id = response.json()["case_id"]
        for filename, doc_type, lines in [
            (
                "contract.txt",
                "CONTRACT_PO",
                [
                    "Commodity: Cotton Yarn",
                    "Amount: USD 1250000",
                    "Currency: USD",
                    "Buyer: Someone Else Ltd.",
                    "Seller: Another Party Inc.",
                    "Incoterm: CIF",
                    "Payment Method: LC at sight",
                    "Final Destination: Dhaka",
                ],
            ),
            (
                "booking.txt",
                "BOOKING_CONFIRMATION",
                [
                    "Vessel: CAPEMOLLINI",
                    "Port of Loading: Shanghai",
                    "Port of Discharge: Chittagong",
                    "ETD: 2026-11-25",
                    "ETA: 2026-12-08",
                ],
            ),
            (
                "lc.txt",
                "LETTER_OF_CREDIT",
                [
                    "LC Number: LC-001",
                    "Applicant: Someone Else Ltd.",
                    "Beneficiary: Another Party Inc.",
                    "Amount: USD 1250000",
                    "Currency: USD",
                    "Latest Shipment: 2026-11-30",
                    "Payment Method: LC at sight",
                ],
            ),
        ]:
            response = self.client.post(
                f"/api/cases/{case_id}/documents/upload",
                data={"document_type": doc_type},
                files={"file": (filename, BytesIO("\n".join(lines).encode("utf-8")), "text/plain")},
            )
            self.assertEqual(response.status_code, 200, response.text)
        fields = self.extract(case_id)
        field = self.perspective_field(fields)
        self.assertEqual(field["value"], "SELLER")
        self.assertEqual(field["detection_source"], "DEFAULT")
        self.approve_all(case_id, fields)
        confirmed = self.confirm(case_id)
        self.assertEqual(confirmed["trade_perspective"], "SELLER")
        self.assertEqual(confirmed["perspective_source"], "DEFAULT")


if __name__ == "__main__":
    unittest.main()
