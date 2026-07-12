import os
import unittest

from app.services.perspective_detection_service import (
    _matches_our_company,
    _normalize_company,
    detect_trade_perspective,
    load_our_company,
)


def _field(field_name: str, value: str, evidence: str | None = None) -> dict:
    return {
        "field_name": field_name,
        "value": value,
        "evidence_text": evidence or f"{field_name.title()}: {value}",
        "source_document_id": "DOC-001",
        "source_document_name": "lc.txt",
    }


class CompanyMatchTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("OUR_COMPANY_NAME", None)
        os.environ.pop("OUR_COMPANY_ALIASES", None)
        load_our_company.cache_clear()

    def test_normalize_strips_case_punctuation_and_suffixes(self) -> None:
        self.assertEqual(_normalize_company("SHANGHAI SOLARIS PV CO., LTD."), "shanghai solaris pv")
        self.assertEqual(_normalize_company("Demo Seller"), "demo seller")

    def test_matches_exact_name_and_aliases(self) -> None:
        self.assertTrue(_matches_our_company("Shanghai Solaris PV Co., Ltd.")[0])
        self.assertTrue(_matches_our_company("SHANGHAI SOLARIS")[0])
        self.assertTrue(_matches_our_company("Solaris PV")[0])

    def test_does_not_match_counterparties(self) -> None:
        self.assertFalse(_matches_our_company("Demo Buyer")[0])
        self.assertFalse(_matches_our_company("Gulf Renewable Energy Trading LLC")[0])
        self.assertFalse(_matches_our_company("Chittagong Alloy Works Ltd.")[0])
        self.assertFalse(_matches_our_company("Shanghai AgriChem Export Co., Ltd.")[0])
        self.assertFalse(_matches_our_company("")[0])

    def test_env_override_replaces_profile(self) -> None:
        os.environ["OUR_COMPANY_NAME"] = "Acme Trading GmbH"
        os.environ["OUR_COMPANY_ALIASES"] = "Acme Trade, Acme"
        load_our_company.cache_clear()
        self.assertTrue(_matches_our_company("ACME TRADING")[0])
        self.assertFalse(_matches_our_company("Shanghai Solaris PV Co., Ltd.")[0])
        os.environ.pop("OUR_COMPANY_NAME", None)
        os.environ.pop("OUR_COMPANY_ALIASES", None)
        load_our_company.cache_clear()


class DetectTradePerspectiveTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("OUR_COMPANY_NAME", None)
        os.environ.pop("OUR_COMPANY_ALIASES", None)
        load_our_company.cache_clear()

    def test_lc_beneficiary_match_yields_seller(self) -> None:
        detection = detect_trade_perspective([
            _field("applicant", "Demo Buyer"),
            _field("beneficiary", "Shanghai Solaris PV Co., Ltd."),
        ])
        self.assertEqual(detection["perspective"], "SELLER")
        self.assertEqual(detection["source"], "AUTO_DETECTED")
        self.assertEqual(detection["confidence"], 0.92)
        self.assertEqual(detection["basis"], "LC Beneficiary · Shanghai Solaris PV Co., Ltd.")
        self.assertIn("Shanghai Solaris", detection["evidence_text"])
        self.assertIn("SELLER seat", detection["evidence_text"])

    def test_lc_applicant_match_yields_buyer(self) -> None:
        detection = detect_trade_perspective([
            _field("applicant", "Shanghai Solaris PV Co., Ltd."),
            _field("beneficiary", "Overseas Supplier Pte. Ltd."),
        ])
        self.assertEqual(detection["perspective"], "BUYER")
        self.assertEqual(detection["basis"], "LC Applicant · Shanghai Solaris PV Co., Ltd.")

    def test_conflicting_votes_use_priority_and_lower_confidence(self) -> None:
        detection = detect_trade_perspective([
            _field("beneficiary", "Shanghai Solaris PV Co., Ltd."),
            _field("buyer", "Shanghai Solaris"),
        ])
        self.assertEqual(detection["perspective"], "SELLER")
        self.assertEqual(detection["confidence"], 0.55)
        self.assertIn("conflicting match on Contract Buyer", detection["evidence_text"])

    def test_lc_basis_preferred_over_contract(self) -> None:
        detection = detect_trade_perspective([
            _field("seller", "Shanghai Solaris PV Co., Ltd."),
            _field("beneficiary", "Shanghai Solaris PV Co., Ltd."),
        ])
        self.assertEqual(detection["basis"], "LC Beneficiary · Shanghai Solaris PV Co., Ltd.")

    def test_no_match_defaults_to_seller(self) -> None:
        detection = detect_trade_perspective([
            _field("applicant", "Someone Else Ltd."),
            _field("beneficiary", "Another Party Inc."),
            _field("vessel", "CAPEMOLLINI"),
        ])
        self.assertEqual(detection["perspective"], "SELLER")
        self.assertEqual(detection["source"], "DEFAULT")
        self.assertEqual(detection["confidence"], 0.4)
        self.assertEqual(detection["basis"], "No company profile match; defaulted to SELLER")

    def test_shipper_and_consignee_vote(self) -> None:
        detection = detect_trade_perspective([_field("consignee", "Shanghai Solaris")])
        self.assertEqual(detection["perspective"], "BUYER")
        self.assertEqual(detection["basis"], "B/L Consignee · Shanghai Solaris")


if __name__ == "__main__":
    unittest.main()
