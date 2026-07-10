import hashlib
from datetime import date, datetime, timezone

from app.services.persistence_service import load_item, save_item

UTC = timezone.utc

URGENCY_ACT_NOW_DAYS = 3
URGENCY_PREPARE_DAYS = 10

URGENCY_POSTURE = {
    "ACT_NOW": "Act now: impact window is imminent; execute the prepared response before the deadline.",
    "PREPARE": "Prepare: line up the fallback plan (rerouting, LC amendment, buyer notice) so it can be executed on short notice.",
    "MONITOR": "Monitor: no action needed yet; the window is far enough out that the forecast may still shift.",
}

TYPE_FAMILY = {
    "WEATHER": "WEATHER",
    "VESSEL_DELAY": "VESSEL",
    "PORT_STRIKE": "PORT",
    "PORT_DISRUPTION": "PORT",
    "PORT_CONGESTION": "PORT",
    "SECURITY": "GEOPOLITICAL",
    "GEOPOLITICAL": "GEOPOLITICAL",
    "TRADE_POLICY": "POLICY",
    "ROUTE_DISRUPTION": "ROUTE",
    "UNKNOWN": "OTHER",
}

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
CLASSIFICATION_RANK = {"Relevant": 2, "Watch": 1, "Irrelevant": 0}

SINGLE_SOURCE_CONFIDENCE_FLOOR = 0.5


def build_hazards(case: dict, events: list[dict], relevance_results: list[dict]) -> tuple[list[dict], list[dict]]:
    event_by_id = {event.get("event_id"): event for event in events}
    result_by_id = {result["event_id"]: result for result in relevance_results}
    clusters: dict[str, list[dict]] = {}
    for result in relevance_results:
        if result["classification"] == "Irrelevant":
            continue
        event = event_by_id.get(result["event_id"], {})
        key = _cluster_key(case, event, result)
        clusters.setdefault(key, []).append(result)

    hazards: list[dict] = []
    for key, cluster_results in clusters.items():
        hazard = _build_hazard(case, key, cluster_results, event_by_id)
        hazards.append(hazard)
        gated = _apply_evidence_gate(hazard, cluster_results)
        for result in gated:
            result_by_id[result["event_id"]] = result

    adjusted_results = [result_by_id[result["event_id"]] for result in relevance_results]
    for hazard in hazards:
        hazard["classification"] = _best_classification(
            [result_by_id[event_id] for event_id in hazard["evidence_event_ids"] if event_id in result_by_id]
        )
        _apply_urgency(hazard)
    hazards.sort(key=lambda hazard: (CLASSIFICATION_RANK.get(hazard["classification"], 0), hazard["confidence"]), reverse=True)
    return hazards, adjusted_results


def apply_hazard_delta(case_id: str, hazards: list[dict]) -> dict:
    previous = [hazard for hazard in (load_item("hazards", case_id) or []) if isinstance(hazard, dict)]
    previous_by_id = {hazard["hazard_id"]: hazard for hazard in previous}
    current_ids = {hazard["hazard_id"] for hazard in hazards}

    new: list[dict] = []
    escalated: list[dict] = []
    ongoing: list[dict] = []
    for hazard in hazards:
        before = previous_by_id.get(hazard["hazard_id"])
        if before is None:
            hazard["lifecycle"] = "NEW"
            new.append(_summary(hazard))
        elif _rank_of(hazard) > _rank_of(before):
            hazard["lifecycle"] = "ESCALATED"
            escalated.append(_summary(hazard))
        else:
            hazard["lifecycle"] = "ONGOING"
            ongoing.append(_summary(hazard))

    resolved = [
        _summary(dict(hazard, lifecycle="RESOLVED"))
        for hazard_id, hazard in previous_by_id.items()
        if hazard_id not in current_ids
    ]

    save_item("hazards", case_id, hazards, case_id)
    return {
        "new": new,
        "escalated": escalated,
        "ongoing": ongoing,
        "resolved": resolved,
        "all_clear": not hazards,
    }


def list_hazards(case_id: str) -> list[dict]:
    return [hazard for hazard in (load_item("hazards", case_id) or []) if isinstance(hazard, dict)]


def hazard_ids_for_events(hazards: list[dict], event_ids: list[str]) -> list[str]:
    wanted = set(event_ids)
    ids = [hazard["hazard_id"] for hazard in hazards if wanted.intersection(hazard["evidence_event_ids"])]
    return list(dict.fromkeys(ids))


def corridor_hazards(case: dict, corridor_states: list[dict]) -> list[dict]:
    from app.services.incoterm_rule_service import attribute_event

    hazards: list[dict] = []
    for state in corridor_states:
        if state.get("state") not in {"AMBER", "RED"}:
            continue
        synthetic_event = {
            "event_id": f"CORR-{state['corridor_id']}",
            "title": f"Corridor risk {state['state']}: {state['name']}",
            "type": "SECURITY",
            "affected_ports": [],
            "affected_region": state["region"],
        }
        attribution = attribute_event(case, synthetic_event)
        classification = "Relevant" if state["state"] == "RED" else "Watch"
        hazard = {
                "hazard_id": f"HAZ-CORR-{state['corridor_id'].upper().replace('-', '')[:12]}",
                "case_id": case.get("case_id"),
                "family": "CORRIDOR",
                "anchor": state["name"].lower(),
                "title": f"{state['name']} corridor risk is {state['state']} ({state['trend']})",
                "classification": classification,
                "severity": "HIGH" if state["state"] == "RED" else "MEDIUM",
                "confidence": 0.8,
                "corroborated": len(state.get("evidence_sources") or []) > 1,
                "sources": ["corridor_risk_service", *(state.get("evidence_sources") or [])],
                "evidence_event_ids": state.get("evidence_event_ids") or [],
                "legs_hit": attribution.get("legs_hit") or ["MAIN_CARRIAGE"],
                "expected_impact_window": None,
                "attribution": attribution,
                "mapped_exposures": ["Shipping"],
                "max_score": None,
                "lifecycle": "NEW",
                "corridor_state": {
                    "corridor_id": state["corridor_id"],
                    "state": state["state"],
                    "trend": state["trend"],
                    "escalation_triggers": state.get("escalation_triggers") or [],
                    "capacity_notes": state.get("capacity_notes") or "",
                },
                "updated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
        _apply_urgency(hazard)
        hazards.append(hazard)
    return hazards


def _apply_urgency(hazard: dict) -> None:
    window = hazard.get("expected_impact_window") or {}
    start = _parse_date(window.get("start"))
    lead_days = (start - date.today()).days if start else None
    if lead_days is None:
        urgency = "PREPARE" if hazard.get("classification") == "Relevant" else "MONITOR"
    elif lead_days <= URGENCY_ACT_NOW_DAYS:
        urgency = "ACT_NOW"
    elif lead_days <= URGENCY_PREPARE_DAYS:
        urgency = "PREPARE"
    else:
        urgency = "MONITOR"
    if hazard.get("classification") == "Watch" and urgency == "ACT_NOW":
        urgency = "PREPARE"
    hazard["lead_days"] = lead_days
    hazard["urgency"] = urgency
    hazard["recommended_posture"] = URGENCY_POSTURE[urgency]


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _cluster_key(case: dict, event: dict, result: dict) -> str:
    family = TYPE_FAMILY.get(str(result.get("event_type") or event.get("type") or "UNKNOWN").upper(), "OTHER")
    if family == "VESSEL":
        anchor = str(case.get("vessel") or "vessel")
    else:
        attribution = result.get("attribution") or {}
        legs = attribution.get("legs_hit") or []
        anchor = (
            str(event.get("affected_region") or "").strip()
            or (event.get("affected_ports") or [""])[0]
            or (legs[0] if legs else "route")
        )
    return f"{family}|{anchor.lower()}"


def _build_hazard(case: dict, key: str, cluster_results: list[dict], event_by_id: dict) -> dict:
    family, anchor = key.split("|", 1)
    best = max(cluster_results, key=lambda result: result.get("score") or 0)
    events = [event_by_id.get(result["event_id"], {}) for result in cluster_results]
    sources = list(dict.fromkeys(str(event.get("source") or "unknown") for event in events))
    max_confidence = max((float(event.get("confidence") or 0) for event in events), default=0.0)
    confidence = min(0.98, max_confidence + 0.1 * (len(sources) - 1))
    severity = max((str(event.get("severity") or "UNKNOWN").upper() for event in events), key=lambda value: SEVERITY_RANK.get(value, 0))
    windows = [event.get("expected_impact_window") for event in events if event.get("expected_impact_window")]
    impact_window = None
    if windows:
        impact_window = {
            "start": min(str(window["start"]) for window in windows),
            "end": max(str(window["end"]) for window in windows),
            "basis": "merged",
        }
    legs: list[str] = []
    for result in cluster_results:
        for leg in (result.get("attribution") or {}).get("legs_hit", []):
            if leg not in legs:
                legs.append(leg)

    hazard_id = "HAZ-" + hashlib.sha1(f"{case.get('case_id')}|{key}".encode("utf-8")).hexdigest()[:8].upper()
    for result in cluster_results:
        result["hazard_id"] = hazard_id

    return {
        "hazard_id": hazard_id,
        "case_id": case.get("case_id"),
        "family": family,
        "anchor": anchor,
        "title": best.get("title"),
        "classification": _best_classification(cluster_results),
        "severity": severity,
        "confidence": round(confidence, 2),
        "corroborated": len(sources) > 1,
        "sources": sources,
        "evidence_event_ids": [result["event_id"] for result in cluster_results],
        "legs_hit": legs,
        "expected_impact_window": impact_window,
        "attribution": best.get("attribution"),
        "mapped_exposures": list(dict.fromkeys(exposure for result in cluster_results for exposure in result.get("mapped_exposures", []))),
        "max_score": best.get("score"),
        "lifecycle": "NEW",
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def _apply_evidence_gate(hazard: dict, cluster_results: list[dict]) -> list[dict]:
    if hazard["corroborated"] or hazard["confidence"] >= SINGLE_SOURCE_CONFIDENCE_FLOOR:
        return cluster_results
    gated: list[dict] = []
    for result in cluster_results:
        if result["classification"] != "Relevant":
            gated.append(result)
            continue
        factors = set(result.get("matched_factors") or [])
        if factors.intersection({"vessel_match", "watched_port_match"}):
            gated.append(result)
            continue
        downgraded = dict(result)
        downgraded["classification"] = "Watch"
        downgraded["matched_factors"] = [*result.get("matched_factors", []), "single_source_low_confidence"]
        downgraded["explanation"] = (
            f"{result.get('title')} matched the route, but is a single low-confidence source without "
            "independent corroboration; held at Watch until corroborated."
        )
        gated.append(downgraded)
    return gated


def _best_classification(results: list[dict]) -> str:
    best = "Watch"
    best_rank = 0
    for result in results:
        rank = CLASSIFICATION_RANK.get(result.get("classification"), 0)
        if rank > best_rank:
            best_rank = rank
            best = result["classification"]
    return best


def _rank_of(hazard: dict) -> tuple[int, int]:
    return (
        CLASSIFICATION_RANK.get(str(hazard.get("classification")), 0),
        SEVERITY_RANK.get(str(hazard.get("severity") or "UNKNOWN").upper(), 0),
    )


def _summary(hazard: dict) -> dict:
    return {
        "hazard_id": hazard["hazard_id"],
        "title": hazard.get("title"),
        "family": hazard.get("family"),
        "classification": hazard.get("classification"),
        "severity": hazard.get("severity"),
        "lifecycle": hazard.get("lifecycle"),
    }
