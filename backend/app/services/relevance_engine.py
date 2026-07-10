from datetime import date, datetime, timedelta

from app.services.incoterm_rule_service import attribute_event
from app.services.route_region_service import (
    event_text_mentions_corridor,
    merge_watched_route_regions,
)
from app.services.risk_mapper import map_event_to_exposures


def classify_events(case: dict, events: list[dict]) -> list[dict]:
    return [classify_event(case, event) for event in events]


def classify_event(case: dict, event: dict) -> dict:
    score = 0
    matched_factors: list[str] = []
    watched_ports = {case["port_of_loading"], case["port_of_discharge"], case["final_destination"]}
    watched_ports.discard(None)
    watched_ports.discard("")
    watched_ports.discard("TBD")
    affected_ports = set(event.get("affected_ports") or [])
    effective_regions = _effective_watched_regions(case)

    vessel = case.get("vessel")
    affected_vessel = event.get("affected_vessel")
    affected_vessels = event.get("affected_vessels") or []
    has_vessel_match = bool(vessel) and (
        affected_vessel == vessel or vessel in affected_vessels
    )
    if has_vessel_match:
        score += 50
        matched_factors.append("vessel_match")

    has_port_match = bool(affected_ports.intersection(watched_ports))
    if has_port_match:
        score += 35
        matched_factors.append("watched_port_match")

    affected_region = event.get("affected_region")
    has_region_match = affected_region in effective_regions
    if not has_region_match and event_text_mentions_corridor(event, effective_regions):
        has_region_match = True
        matched_factors.append("route_corridor_text_match")
    if has_region_match:
        score += 25
        if "route_corridor_text_match" not in matched_factors:
            matched_factors.append("route_region_match")
    elif not has_vessel_match and not has_port_match:
        score -= 40
        matched_factors.append("unrelated_region")

    if affected_ports and not has_port_match and not has_vessel_match and not has_region_match:
        score -= 50
        matched_factors.append("unrelated_port")

    hard_unrelated = (
        not has_vessel_match
        and not has_port_match
        and not has_region_match
        and ("unrelated_region" in matched_factors or "unrelated_port" in matched_factors)
    )

    if not hard_unrelated and _is_near_shipment_window(case, event):
        score += 20
        matched_factors.append("shipment_window_overlap")

    if not hard_unrelated and _affects_deadline(event):
        score += 20
        matched_factors.append("eta_or_deadline_impact")

    if not hard_unrelated and str(event.get("severity", "")).upper() in {"HIGH", "CRITICAL"}:
        score += 10
        matched_factors.append("high_severity")

    voyage_aligned = bool(event.get("voyage_aligned"))
    if not hard_unrelated and voyage_aligned:
        score += 15
        matched_factors.append("voyage_alignment_match")

    if event["type"] == "WEATHER" and "vessel_match" not in matched_factors:
        departure_threat = has_port_match and "shipment_window_overlap" in matched_factors
        if not departure_threat and not voyage_aligned:
            score = min(score, 60)
            matched_factors.append("weather_watch_cap")

    confidence = event.get("confidence")
    if confidence is not None and score > 0:
        try:
            factor = 0.6 + 0.4 * max(0.0, min(float(confidence), 1.0))
            decay = _forecast_horizon_decay(event)
            if decay < 1.0:
                factor *= decay
                matched_factors.append("forecast_horizon_decay")
            score = round(score * factor)
            matched_factors.append("confidence_weighted")
        except (TypeError, ValueError):
            pass

    classification = _classification(score)
    attribution = attribute_event(case, event)
    if classification == "Relevant" and not attribution["monitor_worthy"]:
        classification = "Watch"
        matched_factors.append("incoterm_risk_not_ours")
    mapped_exposures = map_event_to_exposures(event, classification, case)

    return {
        "event_id": event["event_id"],
        "title": event["title"],
        "classification": classification,
        "score": score,
        "raw_score": score,
        "display_score": max(0, min(score, 100)),
        "matched_factors": matched_factors,
        "explanation": _explain(event, classification, mapped_exposures, attribution),
        "mapped_exposures": mapped_exposures,
        "attribution": attribution,
        "delay_days": event.get("delay_days"),
        "expected_impact_window": event.get("expected_impact_window"),
        "source": event.get("source"),
        "source_type": event.get("source_type"),
        "event_type": event.get("event_type") or event.get("type"),
        "url": event.get("url"),
        "confidence": event.get("confidence"),
    }


def _effective_watched_regions(case: dict) -> set[str]:
    return set(merge_watched_route_regions(case))


def _classification(score: int) -> str:
    if score >= 70:
        return "Relevant"
    if score >= 35:
        return "Watch"
    return "Irrelevant"


def _is_near_shipment_window(case: dict, event: dict) -> bool:
    etd = _parse_date_like(case.get("etd"))
    eta = _parse_date_like(case.get("eta"))
    if not etd or not eta:
        return False
    voyage_start = etd - timedelta(days=3)
    voyage_end = eta + timedelta(days=3)

    window = event.get("expected_impact_window") or {}
    impact_start = _parse_date_like(window.get("start"))
    impact_end = _parse_date_like(window.get("end"))
    if impact_start and impact_end:
        return impact_start <= voyage_end and impact_end >= voyage_start

    event_date = _parse_date_like(event.get("event_time"))
    if not event_date:
        return False
    return voyage_start <= event_date <= voyage_end


def _parse_date_like(value) -> date | None:
    if value in {None, ""}:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


FORECAST_WINDOW_BASES = {"forecast", "forecast_voyage_aligned", "typhoon_forecast"}


def _forecast_horizon_decay(event: dict) -> float:
    window = event.get("expected_impact_window") or {}
    if str(window.get("basis") or "") not in FORECAST_WINDOW_BASES:
        return 1.0
    start = _parse_date_like(window.get("start"))
    if not start:
        return 1.0
    lead_days = (start - date.today()).days
    if lead_days <= 0:
        return 1.0
    return max(0.55, 1 - 0.03 * lead_days)


def _affects_deadline(event: dict) -> bool:
    if event["type"] == "VESSEL_DELAY" and int(event.get("delay_days") or 0) >= 3:
        return True
    impact = event.get("impact", "").lower()
    return "eta" in impact or "latest shipment" in impact or "departure delay" in impact or "transit delay" in impact


def _explain(event: dict, classification: str, mapped_exposures: list[str], attribution: dict) -> str:
    if classification == "Irrelevant":
        return "Filtered out because it does not overlap with the watched vessel, ports, or route corridor."

    exposure_text = ", ".join(mapped_exposures) if mapped_exposures else "no direct exposure"
    if classification == "Relevant":
        return f"{event['title']} directly matches the case watch profile and maps to {exposure_text}. {attribution['attribution_note']}"
    if not attribution["monitor_worthy"] and attribution["legs_hit"]:
        return (
            f"{event['title']} overlaps the route, but under {attribution['incoterm']} the affected leg is not "
            f"{attribution['trade_perspective']}'s risk and {attribution['trade_perspective']} cannot act on it; monitor as Watch. "
            f"{attribution['attribution_note']}"
        )
    return f"{event['title']} overlaps the case route or shipment window, but lacks a confirmed vessel delay or direct disruption; monitor as Watch."
