import os
import unittest
from datetime import date, timedelta

from app.services.case_service import create_demo_case, reset_store
from app.services.corridor_risk_service import (
    corridors_for_case,
    seasonal_baseline,
    update_corridor_states,
    update_port_states,
)
from app.services.document_service import reset_document_store
from app.services.event_connectors.typhoon_track_connector import TyphoonTrackConnector
from app.services.hazard_service import corridor_hazards
from app.services.policy_registry_service import match_policies_for_case
from app.services.relevance_engine import classify_event
from app.services.risk_calendar_service import calendar_events_for_case
from app.services.voyage_schedule_service import build_voyage_schedule, position_on, region_transit_windows


class VoyageScheduleTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case(imminent=True)

    def test_daily_positions_cover_voyage(self) -> None:
        schedule = build_voyage_schedule(self.case)
        positions = schedule["positions"]
        self.assertTrue(positions)
        self.assertEqual(positions[0]["date"], self.case["etd"])
        self.assertEqual(positions[-1]["date"], self.case["eta"])
        self.assertAlmostEqual(positions[0]["lat"], 31.23, delta=0.5)
        self.assertAlmostEqual(positions[-1]["lat"], 22.36, delta=0.5)
        dates = [position["date"] for position in positions]
        self.assertEqual(dates, sorted(dates))

    def test_position_on_and_transit_windows(self) -> None:
        schedule = build_voyage_schedule(self.case)
        etd = date.fromisoformat(self.case["etd"])
        self.assertIsNotNone(position_on(schedule, etd))
        self.assertIsNone(position_on(schedule, etd - timedelta(days=30)))
        windows = region_transit_windows(schedule)
        self.assertTrue(windows)
        self.assertEqual(windows[0]["start"], self.case["etd"])

    def test_fail_soft_without_dates(self) -> None:
        broken = dict(self.case, etd="", eta="")
        schedule = build_voyage_schedule(broken)
        self.assertEqual(schedule["positions"], [])
        self.assertTrue(schedule["warnings"])


class TyphoonConnectorTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TYPHOON_SOURCE_MODE"] = "MOCK"
        os.environ["TYPHOON_ENABLED"] = "true"
        reset_store()
        reset_document_store()

    def tearDown(self) -> None:
        os.environ.pop("TYPHOON_SOURCE_MODE", None)
        os.environ.pop("TYPHOON_ENABLED", None)

    def test_fixture_storm_hits_imminent_voyage(self) -> None:
        case = create_demo_case(imminent=True)
        events = TyphoonTrackConnector().fetch_events({}, case["case_id"])
        self.assertTrue(events)
        for event in events:
            self.assertTrue(event["voyage_aligned"])
            self.assertEqual(event["expected_impact_window"]["basis"], "typhoon_forecast")
        crossing = next(event for event in events if "crosses route" in event["title"])
        points = crossing["raw_payload"]["storm"]["points"]
        self.assertGreater(points[-1]["cone_radius_km"], points[0]["cone_radius_km"])

    def test_far_future_voyage_gets_no_typhoon_events(self) -> None:
        case = create_demo_case()
        events = TyphoonTrackConnector().fetch_events({}, case["case_id"])
        self.assertEqual(events, [])

    def test_off_mode_disables_connector(self) -> None:
        os.environ["TYPHOON_SOURCE_MODE"] = "OFF"
        case = create_demo_case(imminent=True)
        connector = TyphoonTrackConnector()
        self.assertEqual(connector.fetch_events({}, case["case_id"]), [])
        self.assertFalse(connector.last_result["enabled"])


class CorridorStateTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case(imminent=True)

    def test_multi_source_security_events_escalate_corridor(self) -> None:
        events = [
            {"event_id": "E1", "type": "SECURITY", "title": "Attack near Strait of Hormuz", "affected_region": "Strait of Hormuz", "confidence": 0.7, "source": "gdelt_event_connector"},
            {"event_id": "E2", "type": "SECURITY", "title": "Hormuz transit incident reported", "affected_region": "", "description": "Tanker incident in hormuz area", "confidence": 0.6, "source": "real_search_event_connector"},
        ]
        states = {state["corridor_id"]: state for state in update_corridor_states(events)}
        self.assertEqual(states["strait-of-hormuz"]["state"], "RED")
        self.assertEqual(states["strait-of-hormuz"]["trend"], "UP")

    def test_no_events_falls_back_to_baseline(self) -> None:
        states = {state["corridor_id"]: state for state in update_corridor_states([])}
        self.assertEqual(states["red-sea"]["state"], "AMBER")
        self.assertEqual(states["strait-of-malacca"]["state"], "GREEN")

    def test_corridors_for_case_maps_route(self) -> None:
        update_corridor_states([])
        schedule = build_voyage_schedule(self.case)
        on_route = {state["corridor_id"] for state in corridors_for_case(self.case, schedule)}
        self.assertIn("east-china-sea", on_route)
        self.assertIn("bay-of-bengal", on_route)
        self.assertNotIn("panama-canal", on_route)

    def test_corridor_hazards_from_states(self) -> None:
        states = [
            {"corridor_id": "red-sea", "name": "Red Sea / Bab el-Mandeb", "region": "Red Sea", "state": "RED", "trend": "UP", "evidence_event_ids": ["E1"], "evidence_sources": ["a", "b"], "escalation_triggers": [], "capacity_notes": ""},
            {"corridor_id": "suez-canal", "name": "Suez Canal", "region": "Suez Canal", "state": "AMBER", "trend": "STABLE", "evidence_event_ids": [], "evidence_sources": [], "escalation_triggers": [], "capacity_notes": ""},
            {"corridor_id": "strait-of-malacca", "name": "Strait of Malacca", "region": "Malacca Strait", "state": "GREEN", "trend": "STABLE", "evidence_event_ids": [], "evidence_sources": [], "escalation_triggers": [], "capacity_notes": ""},
        ]
        hazards = corridor_hazards(self.case, states)
        self.assertEqual(len(hazards), 2)
        by_id = {hazard["corridor_state"]["corridor_id"]: hazard for hazard in hazards}
        self.assertEqual(by_id["red-sea"]["classification"], "Relevant")
        self.assertEqual(by_id["suez-canal"]["classification"], "Watch")

    def test_port_states_from_events_and_calendar(self) -> None:
        events = [
            {"event_id": "E1", "type": "PORT_DISRUPTION", "affected_ports": ["Chittagong"], "confidence": 0.6},
            {"event_id": "E2", "type": "PORT_CONGESTION", "affected_ports": ["Chittagong"], "confidence": 0.6},
        ]
        states = {state["port"]: state for state in update_port_states(["Shanghai", "Chittagong"], events)}
        self.assertEqual(states["Chittagong"]["state"], "RED")
        self.assertEqual(states["Shanghai"]["state"], "GREEN")

    def test_seasonal_baseline_for_summer_voyage(self) -> None:
        schedule = build_voyage_schedule(self.case)
        advisories = seasonal_baseline(schedule)
        regions = {advisory["region"] for advisory in advisories}
        self.assertIn("East China Sea", regions)


class RiskCalendarTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()

    def test_november_voyage_hits_labor_window(self) -> None:
        case = create_demo_case()
        events = calendar_events_for_case(case, build_voyage_schedule(case))
        ids = {event["raw_payload"]["calendar_entry"]["calendar_id"] for event in events}
        self.assertIn("CAL-CTG-LABOR", ids)

    def test_summer_voyage_has_no_cny_event(self) -> None:
        case = create_demo_case(imminent=True)
        events = calendar_events_for_case(case, build_voyage_schedule(case))
        ids = {event["raw_payload"]["calendar_entry"]["calendar_id"] for event in events}
        self.assertNotIn("CAL-CNY", ids)

    def test_low_severity_entries_get_low_confidence(self) -> None:
        case = create_demo_case()
        events = calendar_events_for_case(case, build_voyage_schedule(case))
        cic = [event for event in events if event["raw_payload"]["calendar_entry"]["calendar_id"] == "CAL-TOKYO-MOU-CIC"]
        for event in cic:
            self.assertEqual(event["confidence"], 0.55)

    def test_all_calendar_events_carry_impact_window(self) -> None:
        case = create_demo_case()
        for event in calendar_events_for_case(case, build_voyage_schedule(case)):
            window = event["expected_impact_window"]
            self.assertLessEqual(window["start"], window["end"])
            self.assertEqual(window["basis"], "calendar")


class PolicyRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case()

    def test_cotton_yarn_investigation_matches_demo_case(self) -> None:
        matches = match_policies_for_case(self.case, build_voyage_schedule(self.case))
        pending_ids = {event["raw_payload"]["policy"]["policy_id"] for event in matches["pending_policy_events"]}
        self.assertIn("POL-BD-COTTON-SG", pending_ids)
        event = next(item for item in matches["pending_policy_events"] if item["raw_payload"]["policy"]["policy_id"] == "POL-BD-COTTON-SG")
        self.assertEqual(event["event_type"], "TRADE_POLICY")
        self.assertEqual(event["expected_impact_window"]["basis"], "policy_stage")
        self.assertIn(event["confidence"], {0.5, 0.7, 0.85, 1.0})

    def test_commodity_mismatch_excludes_policy(self) -> None:
        case = dict(self.case, commodity="Consumer electronics")
        matches = match_policies_for_case(case, None)
        pending_ids = {event["raw_payload"]["policy"]["policy_id"] for event in matches["pending_policy_events"]}
        self.assertNotIn("POL-BD-COTTON-SG", pending_ids)

    def test_active_regional_policy_requires_region_on_route(self) -> None:
        matches = match_policies_for_case(self.case, build_voyage_schedule(self.case))
        active_ids = {policy["policy_id"] for policy in matches["active_policies"]}
        self.assertNotIn("POL-RED-SEA-WRA", active_ids)
        red_sea_case = dict(self.case, route="Shanghai -> Red Sea -> Rotterdam")
        matches = match_policies_for_case(red_sea_case, None)
        active_ids = {policy["policy_id"] for policy in matches["active_policies"]}
        self.assertIn("POL-RED-SEA-WRA", active_ids)


class ForecastRelevanceTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case(imminent=True)
        etd = date.fromisoformat(self.case["etd"])
        self.window = {"start": (etd + timedelta(days=2)).isoformat(), "end": (etd + timedelta(days=3)).isoformat()}

    def _weather_event(self, **overrides) -> dict:
        event = {
            "event_id": "EVT-FC",
            "title": "Gale forecast over route",
            "type": "WEATHER",
            "event_time": self.window["start"],
            "affected_ports": [],
            "affected_region": "East China Sea",
            "severity": "HIGH",
            "confidence": 0.8,
            "impact": "Forecast gale; possible transit delay",
        }
        event.update(overrides)
        return event

    def test_voyage_aligned_event_escapes_weather_cap(self) -> None:
        aligned = classify_event(self.case, self._weather_event(
            voyage_aligned=True,
            expected_impact_window={**self.window, "basis": "forecast_voyage_aligned"},
        ))
        self.assertIn("voyage_alignment_match", aligned["matched_factors"])
        self.assertNotIn("weather_watch_cap", aligned["matched_factors"])
        self.assertEqual(aligned["classification"], "Relevant")

        unaligned = classify_event(self.case, self._weather_event())
        self.assertIn("weather_watch_cap", unaligned["matched_factors"])
        self.assertLess(unaligned["score"], aligned["score"])

    def test_forecast_horizon_decay_lowers_far_forecasts(self) -> None:
        near = classify_event(self.case, self._weather_event(
            voyage_aligned=True,
            expected_impact_window={**self.window, "basis": "forecast_voyage_aligned"},
        ))
        far_start = (date.today() + timedelta(days=14)).isoformat()
        far = classify_event(self.case, self._weather_event(
            voyage_aligned=True,
            expected_impact_window={"start": far_start, "end": far_start, "basis": "forecast_voyage_aligned"},
        ))
        self.assertIn("forecast_horizon_decay", far["matched_factors"])
        self.assertLess(far["score"], near["score"])

    def test_announced_dates_do_not_decay(self) -> None:
        announced = classify_event(self.case, self._weather_event(
            expected_impact_window={**self.window, "basis": "explicit"},
        ))
        self.assertNotIn("forecast_horizon_decay", announced["matched_factors"])


class UrgencyTierTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_store()
        self.case = create_demo_case(imminent=True)

    def _hazards_for_window(self, start_offset_days: int) -> list[dict]:
        from app.services.hazard_service import build_hazards

        start = (date.today() + timedelta(days=start_offset_days)).isoformat()
        events = [{
            "event_id": "EVT-U1",
            "title": "Forecast disruption",
            "type": "WEATHER",
            "source": "open_meteo_weather_connector",
            "confidence": 0.8,
            "affected_ports": ["Shanghai"],
            "affected_region": "East China Sea",
            "severity": "HIGH",
            "voyage_aligned": True,
            "expected_impact_window": {"start": start, "end": start, "basis": "forecast_voyage_aligned"},
            "impact": "possible departure delay",
        }]
        from app.services.relevance_engine import classify_events

        hazards, _ = build_hazards(self.case, events, classify_events(self.case, events))
        return hazards

    def test_imminent_window_is_act_now(self) -> None:
        hazard = self._hazards_for_window(2)[0]
        self.assertEqual(hazard["urgency"], "ACT_NOW")
        self.assertEqual(hazard["lead_days"], 2)

    def test_mid_window_is_prepare(self) -> None:
        hazard = self._hazards_for_window(7)[0]
        self.assertEqual(hazard["urgency"], "PREPARE")

    def test_far_window_is_monitor(self) -> None:
        hazard = self._hazards_for_window(14)[0]
        self.assertEqual(hazard["urgency"], "MONITOR")
        self.assertIn("recommended_posture", hazard)


if __name__ == "__main__":
    unittest.main()
