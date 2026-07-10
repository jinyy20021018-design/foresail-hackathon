import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.services.port_registry_service import resolve_port

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "policy_registry.json"

STAGE_CONFIDENCE = {
    "INITIATION": 0.5,
    "PRELIMINARY_DETERMINATION": 0.7,
    "FINAL_DETERMINATION": 0.85,
    "EFFECTIVE": 1.0,
}


@lru_cache(maxsize=1)
def load_policy_registry() -> list[dict]:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def match_policies_for_case(case: dict, schedule: dict | None = None) -> dict:
    active: list[dict] = []
    pending_events: list[dict] = []
    for policy in load_policy_registry():
        if not _scope_matches(policy["scope"], case, schedule):
            continue
        if policy["status"] == "ACTIVE":
            active.append(_active_exposure(policy, case))
        else:
            event = _pending_policy_event(policy, case)
            if event:
                pending_events.append(event)
    return {"active_policies": active, "pending_policy_events": pending_events}


def _scope_matches(scope: dict, case: dict, schedule: dict | None) -> bool:
    origin_countries = [country.upper() for country in scope.get("origin_countries") or []]
    destination_countries = [country.upper() for country in scope.get("destination_countries") or []]
    keywords = [keyword.lower() for keyword in scope.get("commodity_keywords") or []]
    regions = {region.lower() for region in scope.get("regions") or []}

    if origin_countries:
        origin = _country_of(case.get("port_of_loading"))
        if not origin or origin not in origin_countries:
            return False
    if destination_countries:
        destination = _country_of(case.get("port_of_discharge")) or _country_of(case.get("final_destination"))
        if not destination or destination not in destination_countries:
            return False
    if keywords:
        commodity = str(case.get("commodity") or "").lower()
        if not commodity or not any(keyword in commodity for keyword in keywords):
            return False
    if regions:
        route_regions = {str(region).lower() for region in _case_regions(case, schedule)}
        if not regions.intersection(route_regions):
            return False
    return True


def _active_exposure(policy: dict, case: dict) -> dict:
    return {
        "policy_id": policy["policy_id"],
        "policy_type": policy["policy_type"],
        "title": policy["title"],
        "severity": policy.get("severity") or "MEDIUM",
        "status": "ACTIVE",
        "effective_date": policy.get("effective_date"),
        "note": policy.get("note") or "",
        "source_url": policy.get("source_url"),
    }


def _pending_policy_event(policy: dict, case: dict) -> dict | None:
    today = date.today()
    stages = policy.get("stages") or []
    upcoming = [stage for stage in stages if _parse_date(stage.get("date")) and _parse_date(stage["date"]) >= today]
    passed = [stage for stage in stages if _parse_date(stage.get("date")) and _parse_date(stage["date"]) < today]
    next_stage = upcoming[0] if upcoming else None
    reached_stage = passed[-1]["stage"] if passed else "INITIATION"
    confidence = STAGE_CONFIDENCE.get(reached_stage, 0.5)

    window_start = next_stage["date"] if next_stage else policy.get("effective_date")
    if not window_start:
        return None
    eta = _parse_date(case.get("eta"))
    window_end = policy.get("effective_date") or window_start

    return {
        "event_id": f"EVT-POLICY-{policy['policy_id']}",
        "source": "policy_registry_connector",
        "source_type": "POLICY",
        "event_type": "TRADE_POLICY",
        "title": policy["title"],
        "description": (
            f"{policy.get('note') or policy['title']} Current stage reached: {reached_stage}; "
            f"next stage {next_stage['stage']} on {next_stage['date']}." if next_stage else policy.get("note") or policy["title"]
        ),
        "event_time": window_start,
        "published_at": today.isoformat(),
        "locations": [case.get("port_of_discharge") or ""],
        "affected_ports": [case.get("port_of_discharge")] if case.get("port_of_discharge") else [],
        "affected_routes": [],
        "affected_vessels": [],
        "affected_region": _region_of(case.get("port_of_discharge")) or "",
        "severity": policy.get("severity") or "MEDIUM",
        "confidence": confidence,
        "expected_impact_window": {"start": str(window_start), "end": str(window_end), "basis": "policy_stage"},
        "url": policy.get("source_url"),
        "raw_payload": {
            "policy": policy,
            "policy_stage_timeline": stages,
            "stage_reached": reached_stage,
            "eta_after_next_stage": bool(eta and next_stage and eta >= _parse_date(next_stage["date"])),
        },
        "dedup_key": f"POLICY|{policy['policy_id']}",
        "impact": (
            f"Shipments arriving after {window_start} may face new duties, holds, or document requirements under this measure."
        ),
    }


def _case_regions(case: dict, schedule: dict | None) -> list[str]:
    from app.services.route_region_service import merge_watched_route_regions

    regions = list(merge_watched_route_regions(case))
    if schedule:
        regions.extend(position.get("region") or "" for position in schedule.get("positions", []))
    return [region for region in regions if region]


def _country_of(port_name) -> str | None:
    record = resolve_port(port_name)
    if not record or not record.get("unlocode"):
        return None
    return str(record["unlocode"])[:2].upper()


def _region_of(port_name) -> str | None:
    record = resolve_port(port_name)
    return record["region"] if record else None


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
