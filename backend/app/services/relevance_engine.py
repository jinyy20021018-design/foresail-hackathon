from datetime import date, datetime, timedelta

from app.services.incoterm_rule_service import attribute_event
from app.services.llm_relevance_factor_service import build_factor_metadata
from app.services.route_region_service import (
    event_text_mentions_corridor,
    merge_watched_route_regions,
)
from app.services.risk_mapper import map_event_to_exposures


FACTOR_LABELS = {
    "vessel_match": "Vessel named in event",
    "watched_port_match": "Hits a watched port",
    "route_region_match": "On a watched sea region",
    "route_corridor_text_match": "Mentions a watched corridor",
    "unrelated_region": "Region off our route",
    "unrelated_port": "Port off our route",
    "shipment_window_overlap": "Inside the shipment window",
    "eta_or_deadline_impact": "Impacts ETA / a deadline",
    "high_severity": "High / critical severity",
    "voyage_alignment_match": "Aligned with vessel's position",
    "weather_watch_cap": "Weather capped to Watch",
    "forecast_horizon_decay": "Forecast horizon decay",
    "confidence_weighted": "Weighted by source confidence",
    "incoterm_risk_not_ours": "Not our risk under Incoterm",
}


def classify_events(case: dict, events: list[dict]) -> list[dict]:
    return [classify_event(case, event) for event in events]


def classify_event(case: dict, event: dict) -> dict:
    score = 0
    matched_factors: list[str] = []
    breakdown: list[dict] = []

    def record(factor: str, delta: int, kind: str = "add") -> None:
        matched_factors.append(factor)
        breakdown.append({
            "factor": factor,
            "label": FACTOR_LABELS.get(factor, factor.replace("_", " ")),
            "delta": int(delta),
            "kind": kind,
            "running": int(score),
        })

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
        record("vessel_match", 50)

    has_port_match = bool(affected_ports.intersection(watched_ports))
    if has_port_match:
        score += 35
        record("watched_port_match", 35)

    affected_region = event.get("affected_region")
    has_region_match = affected_region in effective_regions
    region_via_text = False
    if not has_region_match and event_text_mentions_corridor(event, effective_regions):
        has_region_match = True
        region_via_text = True
    if has_region_match:
        score += 25
        record("route_corridor_text_match" if region_via_text else "route_region_match", 25)
    elif not has_vessel_match and not has_port_match:
        score -= 40
        record("unrelated_region", -40)

    if affected_ports and not has_port_match and not has_vessel_match and not has_region_match:
        score -= 50
        record("unrelated_port", -50)

    hard_unrelated = (
        not has_vessel_match
        and not has_port_match
        and not has_region_match
        and ("unrelated_region" in matched_factors or "unrelated_port" in matched_factors)
    )

    if not hard_unrelated and _is_near_shipment_window(case, event):
        score += 20
        record("shipment_window_overlap", 20)

    if not hard_unrelated and _affects_deadline(event):
        score += 20
        record("eta_or_deadline_impact", 20)

    if not hard_unrelated and str(event.get("severity", "")).upper() in {"HIGH", "CRITICAL"}:
        score += 10
        record("high_severity", 10)

    voyage_aligned = bool(event.get("voyage_aligned"))
    if not hard_unrelated and voyage_aligned:
        score += 15
        record("voyage_alignment_match", 15)

    if _event_type(event) == "WEATHER" and "vessel_match" not in matched_factors:
        departure_threat = has_port_match and "shipment_window_overlap" in matched_factors
        if not departure_threat and not voyage_aligned:
            before = score
            score = min(score, 60)
            record("weather_watch_cap", score - before, kind="cap")

    confidence = event.get("confidence")
    if confidence is not None and score > 0:
        try:
            factor = 0.6 + 0.4 * max(0.0, min(float(confidence), 1.0))
            decay = _forecast_horizon_decay(event)
            before = score
            if decay < 1.0:
                factor *= decay
            score = round(score * factor)
            if decay < 1.0:
                record("forecast_horizon_decay", 0, kind="flag")
            record("confidence_weighted", score - before, kind="scale")
        except (TypeError, ValueError):
            pass

    classification = _classification(score)
    attribution = attribute_event(case, event)
    if classification == "Relevant" and not attribution["monitor_worthy"]:
        classification = "Watch"
        record("incoterm_risk_not_ours", 0, kind="flag")
    mapped_exposures = map_event_to_exposures(event, classification, case)
    factor_metadata = build_factor_metadata(case, event, matched_factors)

    return {
        "event_id": event["event_id"],
        "title": event["title"],
        "classification": classification,
        "score": score,
        "raw_score": score,
        "display_score": max(0, min(score, 100)),
        "matched_factors": matched_factors,
        "factor_breakdown": breakdown,
        "explanation": _explain(event, classification, mapped_exposures, attribution),
        "mapped_exposures": mapped_exposures,
        "attribution": attribution,
        "delay_days": event.get("delay_days"),
        "expected_impact_window": event.get("expected_impact_window"),
        "source": event.get("source"),
        "source_type": event.get("source_type"),
        "event_type": event.get("event_type") or event.get("type"),
        "severity": event.get("severity"),
        "event_time": event.get("event_time"),
        "published_at": event.get("published_at"),
        "url": event.get("url"),
        "confidence": event.get("confidence"),
        **factor_metadata,
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
    if _event_type(event) == "VESSEL_DELAY" and int(event.get("delay_days") or 0) >= 3:
        return True
    impact = event.get("impact", "").lower()
    return "eta" in impact or "latest shipment" in impact or "departure delay" in impact or "transit delay" in impact


def _event_type(event: dict) -> str:
    return str(event.get("event_type") or event.get("type") or "").upper()


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
