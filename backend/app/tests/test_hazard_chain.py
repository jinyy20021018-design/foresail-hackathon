import os
import unittest
from datetime import date, timedelta

from app.services.action_board_service import earliest_action_deadline, generate_actions
from app.services.action_draft_service import generate_action_drafts
from app.services.case_service import create_demo_case, get_case, reset_store, set_monitoring_outputs
from app.services.document_service import reset_document_store
from app.services.event_normalizer import normalize_event
from app.services.hazard_service import apply_hazard_delta, build_hazards
from app.services.mock_event_service import get_mock_events
from app.services.relevance_engine import classify_event, classify_events
from app.services.risk_mapper import map_event_to_exposures
from app.services.search_query_builder import build_external_event_queries
from app.services.status_machine import can_transition


class ImpactWindowTest(unittest.TestCase):
    def test_type_default_window(self) -> None:
        event = normalize_event({"event_id": "E1", "type": "PORT_DISRUPTION", "title": "Strike", "event_time": "2026-11-20"}, "CASE-X")
        window = event["expected_impact_window"]
        self.assertEqual(window["start"], "2026-11-20")
        self.assertEqual(window["end"], "2026-11-27")
        self.assertEqual(window["basis"], "type_default")

    def test_vessel_delay_window_uses_new_eta(self) -> None:
        event = normalize_event(
            {"event_id": "E2", "type": "VESSEL_DELAY", "title": "Delay", "event_time": "2026-11-27", "new_eta": "2026-12-13"},
            "CASE-X",
        )
        self.assertEqual(event["expected_impact_window"]["end"], "2026-12-13")

    def test_future_impact_window_counts_as_shipment_window_overlap(self) -> None:
        reset_store()
        case = create_demo_case()
        event = {
            "event_id": "EVT-FUT",
            "title": "Port workers announce strike for late November",
            "type": "PORT_STRIKE",
            "event_time": "2026-07-01",
            "affected_ports": ["Shanghai"],
            "affected_region": "East China Sea",
            "severity": "HIGH",
            "impact": "Planned strike may cause departure delay at Shanghai",
            "expected_impact_window": {"start": case["etd"], "end": case["eta"], "basis": "explicit"},
        }
        result = classify_event(case, event)
        self.assertIn("shipment_window_overlap", result["matched_factors"])
        self.assertEqual(result["classification"], "Relevant")


class GeoChainTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case()

    def test_geopolitical_event_maps_to_exposures(self) -> None:
        event = {
            "event_id": "EVT-GEO",
            "type": "GEOPOLITICAL",
            "title": "Regional tension in East China Sea",
            "affected_ports": [],
            "affected_region": "East China Sea",
        }
        exposures = map_event_to_exposures(event, "Relevant", self.case)
        self.assertIn("Shipping", exposures)
        self.assertIn("LC Deadline", exposures)

    def test_trade_policy_event_maps_to_trade_compliance(self) -> None:
        event = {
            "event_id": "EVT-POL",
            "type": "TRADE_POLICY",
            "title": "New customs restrictions announced",
            "affected_ports": ["Chittagong"],
            "affected_region": "Bangladesh",
        }
        exposures = map_event_to_exposures(event, "Relevant", self.case)
        self.assertIn("Trade Compliance", exposures)

    def test_query_budget_keeps_geopolitical_query(self) -> None:
        os.environ["EXTERNAL_EVENT_QUERY_LIMIT"] = "3"
        try:
            from app.services.case_service import get_watch_profile

            queries = build_external_event_queries(self.case["case_id"], get_watch_profile(self.case["case_id"]))
            query_types = {query["query_type"] for query in queries}
            self.assertIn("GEOPOLITICAL", query_types)
        finally:
            os.environ.pop("EXTERNAL_EVENT_QUERY_LIMIT", None)


class HazardServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        reset_document_store()
        self.case = create_demo_case()

    def test_mock_events_cluster_into_hazards_with_stable_ids(self) -> None:
        events = get_mock_events()
        results = classify_events(self.case, events)
        hazards, adjusted = build_hazards(self.case, events, results)
        self.assertTrue(hazards)
        self.assertTrue(all(hazard["hazard_id"].startswith("HAZ-") for hazard in hazards))
        again, _ = build_hazards(self.case, events, classify_events(self.case, events))
        self.assertEqual(
            sorted(hazard["hazard_id"] for hazard in hazards),
            sorted(hazard["hazard_id"] for hazard in again),
        )
        relevant_ids = {result["event_id"] for result in adjusted if result["classification"] != "Irrelevant"}
        covered = {event_id for hazard in hazards for event_id in hazard["evidence_event_ids"]}
        self.assertEqual(relevant_ids, covered)

    def test_multi_source_same_anchor_corroborates(self) -> None:
        events = [
            {
                "event_id": "EVT-A",
                "title": "Typhoon nears East China Sea",
                "type": "WEATHER",
                "source": "open_meteo_weather_connector",
                "event_time": "2026-11-24",
                "affected_ports": ["Shanghai"],
                "affected_region": "East China Sea",
                "severity": "HIGH",
                "confidence": 0.75,
                "impact": "Departure delay possible",
            },
            {
                "event_id": "EVT-B",
                "title": "Typhoon warning issued for East China Sea",
                "type": "WEATHER",
                "source": "real_search_event_connector",
                "event_time": "2026-11-24",
                "affected_ports": ["Shanghai"],
                "affected_region": "East China Sea",
                "severity": "HIGH",
                "confidence": 0.6,
                "impact": "Departure delay possible",
            },
        ]
        results = classify_events(self.case, events)
        hazards, _ = build_hazards(self.case, events, results)
        self.assertEqual(len(hazards), 1)
        hazard = hazards[0]
        self.assertTrue(hazard["corroborated"])
        self.assertAlmostEqual(hazard["confidence"], 0.85, places=2)
        self.assertEqual(set(hazard["evidence_event_ids"]), {"EVT-A", "EVT-B"})

    def test_single_low_confidence_source_is_gated_to_watch(self) -> None:
        events = [
            {
                "event_id": "EVT-RUMOR",
                "title": "Unverified report of route trouble",
                "type": "SECURITY",
                "source": "real_search_event_connector",
                "confidence": 0.3,
                "affected_ports": [],
                "affected_region": "East China Sea",
            }
        ]
        results = [
            {
                "event_id": "EVT-RUMOR",
                "title": "Unverified report of route trouble",
                "classification": "Relevant",
                "score": 75,
                "matched_factors": ["route_region_match"],
                "mapped_exposures": ["Shipping"],
                "event_type": "SECURITY",
                "attribution": {"legs_hit": ["MAIN_CARRIAGE"]},
            }
        ]
        hazards, adjusted = build_hazards(self.case, events, results)
        self.assertEqual(adjusted[0]["classification"], "Watch")
        self.assertIn("single_source_low_confidence", adjusted[0]["matched_factors"])
        self.assertEqual(hazards[0]["classification"], "Watch")

    def test_hazard_delta_lifecycle(self) -> None:
        events = get_mock_events()
        results = classify_events(self.case, events)
        hazards, _ = build_hazards(self.case, events, results)
        first = apply_hazard_delta(self.case["case_id"], hazards)
        self.assertEqual(len(first["new"]), len(hazards))
        self.assertFalse(first["resolved"])

        remaining_events = [event for event in events if event["event_id"] != "EVT-003"]
        remaining_results = classify_events(self.case, remaining_events)
        remaining_hazards, _ = build_hazards(self.case, remaining_events, remaining_results)
        second = apply_hazard_delta(self.case["case_id"], remaining_hazards)
        self.assertFalse(second["new"])
        self.assertTrue(second["ongoing"])
        self.assertEqual(len(second["resolved"]), len(hazards) - len(remaining_hazards))

        third = apply_hazard_delta(self.case["case_id"], [])
        self.assertTrue(third["all_clear"])
        self.assertEqual(len(third["resolved"]), len(remaining_hazards))


class ActionDeadlineTest(unittest.TestCase):
    def test_deadline_backcalculated_from_latest_shipment(self) -> None:
        today = date.today()
        latest = (today + timedelta(days=2)).isoformat()
        risk_summary = {"exposures": [{"category": "LC Deadline", "party_perspective": "SELLER", "incoterm_basis": ""}]}
        actions = generate_actions(risk_summary, {"latest_shipment_date": latest}, [])
        self.assertTrue(actions)
        for action in actions:
            self.assertEqual(action["deadline_date"], today.isoformat())
        self.assertEqual(earliest_action_deadline(actions), today.isoformat())

    def test_deadline_defaults_to_label_dates_without_facts(self) -> None:
        risk_summary = {"exposures": [{"category": "Port Operation", "party_perspective": "SELLER", "incoterm_basis": ""}]}
        actions = generate_actions(risk_summary)
        today = date.today()
        labels = {action["deadline"]: action["deadline_date"] for action in actions}
        self.assertEqual(labels.get("Today"), today.isoformat())


class DraftParameterizationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.facts = {
            "case_id": "CASE-EU",
            "vessel": "EVER TEST",
            "route": "Ningbo -> Rotterdam -> Duisburg",
            "port_of_loading": "Ningbo",
            "port_of_discharge": "Rotterdam",
            "final_destination": "Duisburg",
            "eta": "2026-08-20",
            "latest_shipment_date": "2026-08-01",
            "payment_method": "LC at sight",
            "incoterm": "CIF",
            "trade_perspective": "SELLER",
            "amount": 99000,
            "currency": "USD",
        }
        self.risk_summary = {
            "exposures": [
                {"category": "Shipping"},
                {"category": "Port Operation"},
                {"category": "Trade Compliance"},
            ]
        }

    def test_drafts_use_case_ports_not_demo_ports(self) -> None:
        drafts = generate_action_drafts("CASE-EU", self.facts, self.risk_summary, [])
        joined = " ".join(draft["body"] for draft in drafts)
        self.assertNotIn("Chittagong", joined)
        self.assertNotIn("Dhaka", joined)
        self.assertNotIn("Bangladesh", joined)
        self.assertIn("Rotterdam", joined)

    def test_drafts_cite_triggering_hazards(self) -> None:
        hazards = [
            {
                "hazard_id": "HAZ-TEST01",
                "title": "Rotterdam port strike",
                "mapped_exposures": ["Port Operation"],
                "expected_impact_window": {"start": "2026-08-10", "end": "2026-08-15"},
            }
        ]
        drafts = generate_action_drafts("CASE-EU", self.facts, self.risk_summary, [], hazards)
        port_draft = next(draft for draft in drafts if draft["draft_type"] == "PORT_STATUS_INQUIRY")
        self.assertIn("Trigger: Rotterdam port strike", port_draft["body"])
        self.assertIn("HAZ-TEST01", port_draft["hazard_ids"])

    def test_trade_compliance_draft_generated(self) -> None:
        drafts = generate_action_drafts("CASE-EU", self.facts, self.risk_summary, [])
        self.assertIn("TRADE_COMPLIANCE_REVIEW", {draft["draft_type"] for draft in drafts})


class StatusMachineV2Test(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case()
        self.case_id = self.case["case_id"]

    def test_monitoring_can_reescalate(self) -> None:
        self.assertTrue(can_transition("MONITORING", "AT_RISK"))
        self.assertTrue(can_transition("MONITORING", "ACTION_REQUIRED"))

    def test_all_clear_returns_case_to_monitoring(self) -> None:
        triggered_summary = {"triggered": True, "trigger_events": ["EVT-X"], "exposures": [{"category": "Shipping"}]}
        actions = [{"action_id": "ACT-001", "related_exposure": "Shipping"}]
        set_monitoring_outputs(self.case_id, [], triggered_summary, actions)
        self.assertEqual(get_case(self.case_id)["status"], "ACTION_REQUIRED")

        clear_summary = {"triggered": False, "trigger_events": [], "exposures": []}
        delta = {"new": [], "escalated": [], "ongoing": [], "resolved": [{"hazard_id": "HAZ-X"}], "all_clear": True}
        set_monitoring_outputs(self.case_id, [], clear_summary, [], delta)
        self.assertEqual(get_case(self.case_id)["status"], "MONITORING")

    def test_watch_only_run_does_not_force_action_required(self) -> None:
        watch_summary = {"triggered": False, "trigger_events": [], "exposures": [{"category": "Shipping"}]}
        actions = [{"action_id": "ACT-001", "related_exposure": "Shipping"}]
        set_monitoring_outputs(self.case_id, [], watch_summary, actions)
        self.assertEqual(get_case(self.case_id)["status"], "WATCHING")


if __name__ == "__main__":
    unittest.main()
