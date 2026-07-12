import os
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import reset_store
from app.services.document_service import reset_document_store


class HormuzDemoTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["USE_LLM_SUMMARY"] = "false"
        os.environ["REQUIRE_LLM_AGENT"] = "false"
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["EVENT_SOURCE_MODE"] = "MOCK"
        os.environ.pop("USE_LLM_EXTRACTION", None)
        reset_store()
        reset_document_store()
        self.client = TestClient(app)

    def create_hormuz_demo(self) -> str:
        response = self.client.post("/api/cases/demo/hormuz")
        self.assertEqual(response.status_code, 200, response.text)
        case = response.json()
        self.assertEqual(case["vessel"], "GULF HORIZON")
        self.assertEqual(case["incoterm"], "CIF")
        return case["case_id"]

    def test_docx_extraction_finds_critical_fields(self) -> None:
        case_id = self.create_hormuz_demo()
        fields = self.client.get(f"/api/cases/{case_id}/extracted-fields").json()
        values = {field["field_name"]: field["value"] for field in fields}
        self.assertEqual(values["beneficiary"], "Shanghai Solaris PV Co., Ltd")
        self.assertEqual(values["applicant"], "Gulf Renewable Energy Trading LLC")
        self.assertEqual(values["incoterm"], "CIF")
        self.assertEqual(values["incoterm_named_place"], "Jebel Ali")
        self.assertEqual(values["vessel"], "GULF HORIZON")
        self.assertEqual(values["port_of_loading"], "Shanghai")
        self.assertEqual(values["port_of_discharge"], "Jebel Ali")
        self.assertEqual(values["etd"], "2026-07-13")
        self.assertEqual(values["eta"], "2026-08-02")
        self.assertEqual(values["latest_shipment_date"], "2026-07-15")
        self.assertEqual(values["amount"], 1890000)
        self.assertEqual(values["currency"], "USD")
        self.assertIn("LC", str(values["payment_method"]).upper())

    def test_perspective_detected_as_seller_and_confirm_flows(self) -> None:
        case_id = self.create_hormuz_demo()
        fields = self.client.get(f"/api/cases/{case_id}/extracted-fields").json()
        perspective = [field for field in fields if field["field_name"] == "trade_perspective"]
        self.assertEqual(len(perspective), 1)
        self.assertEqual(perspective[0]["value"], "SELLER")
        self.assertEqual(perspective[0]["detection_source"], "AUTO_DETECTED")
        self.assertEqual(perspective[0]["detection_basis"], "LC Beneficiary · Shanghai Solaris PV Co., Ltd")
        for field in fields:
            response = self.client.post(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/approve")
            self.assertEqual(response.status_code, 200, response.text)
        confirmed = self.client.post(f"/api/cases/{case_id}/confirm-fields")
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["trade_perspective"], "SELLER")
        self.assertEqual(confirmed.json()["perspective_source"], "AUTO_DETECTED")

    def test_curated_hormuz_events_hit_the_case(self) -> None:
        case_id = self.create_hormuz_demo()
        fields = self.client.get(f"/api/cases/{case_id}/extracted-fields").json()
        for field in fields:
            self.client.post(f"/api/cases/{case_id}/extracted-fields/{field['field_id']}/approve")
        self.client.post(f"/api/cases/{case_id}/confirm-fields")
        run = self.client.post(f"/api/cases/{case_id}/agent-run")
        self.assertEqual(run.status_code, 200, run.text)
        results = self.client.get(f"/api/cases/{case_id}/relevance-results").json()
        by_id = {result["event_id"]: result for result in results}
        self.assertIn("EVT-201", by_id)
        self.assertEqual(by_id["EVT-201"]["classification"], "Relevant")
        attribution = by_id["EVT-201"].get("attribution") or {}
        self.assertEqual(attribution.get("incoterm"), "CIF")
        self.assertEqual(attribution.get("trade_perspective"), "SELLER")


if __name__ == "__main__":
    unittest.main()
