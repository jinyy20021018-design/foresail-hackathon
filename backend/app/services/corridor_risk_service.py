import json
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.services.persistence_service import load_item, save_item
from app.services.route_region_service import merge_watched_route_regions

UTC = timezone.utc
CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "corridor_config.json"
CLIMATOLOGY_PATH = Path(__file__).resolve().parents[1] / "data" / "climatology.json"

STATE_RANK = {"GREEN": 0, "AMBER": 1, "RED": 2}
CORRIDOR_EVENT_TYPES = {"SECURITY", "GEOPOLITICAL", "ROUTE_DISRUPTION"}
PORT_EVENT_TYPES = {"PORT_DISRUPTION", "PORT_STRIKE", "PORT_CONGESTION"}


@lru_cache(maxsize=1)
def load_corridor_config() -> list[dict]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_climatology() -> list[dict]:
    with CLIMATOLOGY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def update_corridor_states(events: list[dict]) -> list[dict]:
    states: list[dict] = []
    for corridor in load_corridor_config():
        matched = [event for event in events if _event_matches_corridor(event, corridor)]
        signal = round(sum(float(event.get("confidence") or 0.5) for event in matched), 2)
        sources = {str(event.get("source") or "unknown") for event in matched}
        computed = "GREEN"
        if signal >= 1.2 or (len(sources) >= 2 and signal >= 0.8):
            computed = "RED"
        elif signal >= 0.5:
            computed = "AMBER"
        level = computed if STATE_RANK[computed] >= STATE_RANK[corridor["baseline_state"]] else corridor["baseline_state"]

        previous = load_item("corridor_state", corridor["id"]) or {}
        previous_level = str(previous.get("state") or corridor["baseline_state"])
        if STATE_RANK[level] > STATE_RANK.get(previous_level, 0):
            trend = "UP"
        elif STATE_RANK[level] < STATE_RANK.get(previous_level, 0):
            trend = "DOWN"
        else:
            trend = "STABLE"

        state = {
            "corridor_id": corridor["id"],
            "name": corridor["name"],
            "region": corridor["region"],
            "lat": corridor["lat"],
            "lng": corridor["lng"],
            "state": level,
            "baseline_state": corridor["baseline_state"],
            "trend": trend,
            "previous_state": previous_level,
            "signal": signal,
            "evidence_event_ids": [event.get("event_id") for event in matched],
            "evidence_sources": sorted(sources),
            "escalation_triggers": corridor["escalation_triggers"],
            "capacity_notes": corridor.get("capacity_notes") or "",
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        save_item("corridor_state", corridor["id"], state, "GLOBAL")
        states.append(state)
    return states


def list_corridor_states() -> list[dict]:
    states = []
    for corridor in load_corridor_config():
        stored = load_item("corridor_state", corridor["id"])
        if stored:
            states.append(stored)
        else:
            states.append(
                {
                    "corridor_id": corridor["id"],
                    "name": corridor["name"],
                    "region": corridor["region"],
                    "lat": corridor["lat"],
                    "lng": corridor["lng"],
                    "state": corridor["baseline_state"],
                    "baseline_state": corridor["baseline_state"],
                    "trend": "STABLE",
                    "previous_state": corridor["baseline_state"],
                    "signal": 0.0,
                    "evidence_event_ids": [],
                    "evidence_sources": [],
                    "escalation_triggers": corridor["escalation_triggers"],
                    "capacity_notes": corridor.get("capacity_notes") or "",
                    "updated_at": None,
                }
            )
    return states


def corridors_for_case(case: dict, schedule: dict | None = None) -> list[dict]:
    watched = {region.lower() for region in merge_watched_route_regions(case)}
    if schedule:
        watched.update(str(position.get("region") or "").lower() for position in schedule.get("positions", []))
    on_route = []
    for state in list_corridor_states():
        corridor = next(item for item in load_corridor_config() if item["id"] == state["corridor_id"])
        names = {corridor["region"].lower(), corridor["name"].lower(), *[alias.lower() for alias in corridor["aliases"]]}
        if names.intersection(watched):
            on_route.append(state)
    return on_route


def update_port_states(watched_ports: list[str], events: list[dict], calendar_events: list[dict] | None = None) -> list[dict]:
    states: list[dict] = []
    calendar_events = calendar_events or []
    for port in watched_ports:
        if not port or str(port).strip().upper() == "TBD":
            continue
        port_lower = str(port).strip().lower()
        matched = [
            event
            for event in events
            if str(event.get("type") or event.get("event_type") or "").upper() in PORT_EVENT_TYPES
            and any(port_lower in str(affected).lower() or str(affected).lower() in port_lower for affected in (event.get("affected_ports") or []))
        ]
        calendar_hits = [
            event
            for event in calendar_events
            if any(port_lower in str(affected).lower() for affected in (event.get("affected_ports") or []))
        ]
        signal = round(sum(float(event.get("confidence") or 0.5) for event in matched), 2)
        level = "GREEN"
        if signal >= 1.0:
            level = "RED"
        elif signal >= 0.4 or calendar_hits:
            level = "AMBER"

        key = f"port:{port_lower.replace(' ', '-')}"
        previous = load_item("corridor_state", key) or {}
        previous_level = str(previous.get("state") or "GREEN")
        trend = "UP" if STATE_RANK[level] > STATE_RANK.get(previous_level, 0) else ("DOWN" if STATE_RANK[level] < STATE_RANK.get(previous_level, 0) else "STABLE")
        state = {
            "port": port,
            "state": level,
            "trend": trend,
            "previous_state": previous_level,
            "signal": signal,
            "evidence_event_ids": [event.get("event_id") for event in matched] + [event.get("event_id") for event in calendar_hits],
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        save_item("corridor_state", key, state, "GLOBAL")
        states.append(state)
    return states


def seasonal_baseline(schedule: dict) -> list[dict]:
    advisories: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for position in schedule.get("positions", []):
        month = date.fromisoformat(position["date"]).month
        for entry in load_climatology():
            if entry["region"] != position["region"] or month not in entry["months"]:
                continue
            key = (entry["region"], entry["note"])
            if key in seen:
                continue
            seen.add(key)
            advisories.append(
                {
                    "region": entry["region"],
                    "level": entry["level"],
                    "months": entry["months"],
                    "note": entry["note"],
                    "transit_date": position["date"],
                }
            )
    return advisories


def _event_matches_corridor(event: dict, corridor: dict) -> bool:
    event_type = str(event.get("type") or event.get("event_type") or "").upper()
    if event_type not in CORRIDOR_EVENT_TYPES:
        return False
    region = str(event.get("affected_region") or "").lower()
    names = [corridor["region"].lower(), *[alias.lower() for alias in corridor["aliases"]]]
    if region and any(name in region or region in name for name in names):
        return True
    text = " ".join(str(event.get(key) or "") for key in ("title", "description", "impact")).lower()
    return any(name in text for name in names)
