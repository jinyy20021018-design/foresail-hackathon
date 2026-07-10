import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "risk_calendar.json"

TYPE_TO_EVENT_TYPE = {
    "HOLIDAY_CAPACITY": "PORT_DISRUPTION",
    "LABOR_CONTRACT": "PORT_DISRUPTION",
    "ELECTION": "GEOPOLITICAL",
    "PSC_CIC": "TRADE_POLICY",
}


@lru_cache(maxsize=1)
def load_risk_calendar() -> list[dict]:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def calendar_events_for_case(case: dict, schedule: dict) -> list[dict]:
    phases = _voyage_phases(case, schedule)
    if not phases:
        return []
    events: list[dict] = []
    for entry in load_risk_calendar():
        for window in _resolve_windows(entry, phases["overall"]):
            for phase_name in entry.get("affects", []):
                phase = phases.get(phase_name)
                if not phase:
                    continue
                overlap = _intersect(window, phase)
                if not overlap:
                    continue
                if not _location_matches(entry, case, phase_name):
                    continue
                events.append(_calendar_event(entry, case, phase_name, overlap))
                break
    return events


def _calendar_event(entry: dict, case: dict, phase_name: str, overlap: tuple[date, date]) -> dict:
    event_type = TYPE_TO_EVENT_TYPE.get(entry["calendar_type"], "PORT_DISRUPTION")
    location = entry.get("region_or_port") or ""
    severity = str(entry.get("severity") or "MEDIUM").upper()
    confidence = {"HIGH": 0.85, "MEDIUM": 0.8, "LOW": 0.55}.get(severity, 0.8)
    if severity == "LOW":
        impact = f"{entry['note']} Advisory only; monitor for schedule effects."
    elif phase_name == "POL":
        impact = f"{entry['note']} Possible departure delay at the load port in the overlap window."
    elif phase_name in {"POD", "ETA"}:
        impact = f"{entry['note']} Possible discharge or inland delivery slowdown in the overlap window."
    else:
        impact = f"{entry['note']} Possible transit slowdown in the overlap window."
    affected_ports = []
    if phase_name == "POL" and case.get("port_of_loading"):
        affected_ports = [case["port_of_loading"]]
    elif phase_name in {"POD", "ETA"} and case.get("port_of_discharge"):
        affected_ports = [case["port_of_discharge"]]
    return {
        "event_id": f"EVT-CAL-{entry['calendar_id']}-{overlap[0].isoformat()}",
        "source": "risk_calendar_connector",
        "source_type": "POLICY" if event_type == "TRADE_POLICY" else "PORT",
        "event_type": event_type,
        "title": entry["title"],
        "description": f"{entry['note']} Overlaps this shipment's {phase_name} window {overlap[0]} to {overlap[1]}.",
        "event_time": overlap[0].isoformat(),
        "published_at": date.today().isoformat(),
        "locations": [location],
        "affected_ports": affected_ports,
        "affected_routes": [location] if not affected_ports else [],
        "affected_vessels": [],
        "affected_region": location,
        "severity": severity,
        "confidence": confidence,
        "calendar_based": True,
        "expected_impact_window": {"start": overlap[0].isoformat(), "end": overlap[1].isoformat(), "basis": "calendar"},
        "url": None,
        "raw_payload": {"calendar_entry": entry, "phase": phase_name},
        "dedup_key": f"CALENDAR|{entry['calendar_id']}|{overlap[0].isoformat()}",
        "impact": impact,
    }


def _voyage_phases(case: dict, schedule: dict) -> dict | None:
    etd = _parse_date(case.get("etd"))
    eta = _parse_date(case.get("eta"))
    if not etd or not eta:
        return None
    return {
        "POL": (etd - timedelta(days=10), etd + timedelta(days=2)),
        "TRANSIT": (etd, eta),
        "POD": (eta - timedelta(days=2), eta + timedelta(days=7)),
        "ETA": (eta - timedelta(days=2), eta + timedelta(days=7)),
        "overall": (etd - timedelta(days=10), eta + timedelta(days=7)),
    }


def _resolve_windows(entry: dict, overall: tuple[date, date]) -> list[tuple[date, date]]:
    fixed = entry.get("window")
    if fixed:
        start, end = _parse_date(fixed.get("start")), _parse_date(fixed.get("end"))
        return [(start, end)] if start and end else []

    annual = entry.get("annual_window")
    if not annual:
        return []
    windows = []
    for year in range(overall[0].year, overall[1].year + 1):
        start = _annual_date(annual["start"], year)
        end = _annual_date(annual["end"], year)
        if not start or not end:
            continue
        if end < start:
            end = _annual_date(annual["end"], year + 1)
        windows.append((start, end))
    return windows


def _location_matches(entry: dict, case: dict, phase_name: str) -> bool:
    location = str(entry.get("region_or_port") or "").lower()
    if not location:
        return True
    if phase_name == "POL":
        anchor = str(case.get("port_of_loading") or "").lower()
    elif phase_name in {"POD", "ETA"}:
        anchor = " ".join(str(case.get(field) or "") for field in ("port_of_discharge", "final_destination")).lower()
    else:
        anchor = " ".join(str(case.get(field) or "") for field in ("route", "port_of_loading", "port_of_discharge", "final_destination")).lower()
    from app.services.port_registry_service import resolve_port

    if location in anchor or anchor in location:
        return True
    for port_field in ("port_of_loading", "port_of_discharge", "final_destination"):
        record = resolve_port(case.get(port_field))
        if record and location in {record["name"].lower(), record["region"].lower()}:
            if phase_name == "TRANSIT":
                return True
            if phase_name == "POL" and port_field == "port_of_loading":
                return True
            if phase_name in {"POD", "ETA"} and port_field in {"port_of_discharge", "final_destination"}:
                return True
    return False


def _intersect(a: tuple[date, date], b: tuple[date, date]) -> tuple[date, date] | None:
    start = max(a[0], b[0])
    end = min(a[1], b[1])
    return (start, end) if start <= end else None


def _annual_date(month_day: str, year: int) -> date | None:
    try:
        month, day = str(month_day).split("-")
        return date(year, int(month), int(day))
    except (ValueError, TypeError):
        return None


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
