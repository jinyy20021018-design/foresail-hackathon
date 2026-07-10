import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data" / "typhoon_tracks.json"

CONE_BASE_RADIUS_KM = 80
CONE_GROWTH_KM_PER_DAY = 45
POL_PROXIMITY_KM = 250


class TyphoonTrackConnector:
    name = "typhoon_track_connector"

    def __init__(self) -> None:
        self.last_result: dict = {}

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        mode = os.getenv("TYPHOON_SOURCE_MODE", "REAL").upper()
        if os.getenv("TYPHOON_ENABLED", "true").lower() != "true" or mode == "OFF":
            self.last_result = {"enabled": False, "mode": mode, "storms_loaded": 0, "typhoon_events_extracted": 0, "warnings": ["Typhoon connector disabled."]}
            return []

        warnings: list[str] = []
        if mode == "MOCK":
            storms = _load_fixture_storms()
        else:
            storms, warnings = _fetch_real_storms()

        events: list[dict] = []
        if storms:
            events = _events_from_storms(storms, case_id, watch_profile)

        self.last_result = {
            "enabled": True,
            "mode": mode,
            "storms_loaded": len(storms),
            "typhoon_events_extracted": len(events),
            "warnings": warnings,
            "connector_errors": [],
        }
        return events


def _load_fixture_storms() -> list[dict]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    storms = []
    for storm in raw:
        points = []
        for point in storm.get("points", []):
            if "offset_hours" in point:
                moment = now + timedelta(hours=float(point["offset_hours"]))
            else:
                moment = datetime.fromisoformat(str(point["time"]).replace("Z", "+00:00"))
            points.append({"time": moment, "lat": float(point["lat"]), "lng": float(point["lng"]), "max_wind_kt": float(point.get("max_wind_kt") or 0)})
        if len(points) >= 2:
            storms.append({"storm_id": storm.get("storm_id") or storm.get("name"), "name": storm.get("name") or storm.get("storm_id"), "points": points})
    return storms


def _fetch_real_storms() -> tuple[list[dict], list[str]]:
    url = os.getenv("TYPHOON_FEED_URL", "https://www.jma.go.jp/bosai/typhoon/data/targetTc.json")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ForeSail-MVP/3.1"})
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return [], [f"TYPHOON_FEED_UNAVAILABLE: {error}"]

    storms: list[dict] = []
    candidates = payload if isinstance(payload, list) else payload.get("storms") or []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        raw_points = entry.get("track") or entry.get("points") or []
        points = []
        for point in raw_points:
            try:
                moment = datetime.fromisoformat(str(point["time"]).replace("Z", "+00:00"))
                points.append({"time": moment, "lat": float(point["lat"]), "lng": float(point.get("lng", point.get("lon"))), "max_wind_kt": float(point.get("wind_kt") or point.get("max_wind_kt") or 0)})
            except (KeyError, TypeError, ValueError):
                continue
        if len(points) >= 2:
            storms.append({"storm_id": entry.get("storm_id") or entry.get("name"), "name": entry.get("name") or entry.get("storm_id") or "Unnamed TC", "points": points})

    if not storms:
        return [], ["TYPHOON_FEED_NO_PARSEABLE_TRACKS: feed reachable but no track data in a supported format."]
    return storms, []


def _events_from_storms(storms: list[dict], case_id: str, watch_profile: dict) -> list[dict]:
    from app.services.case_service import get_case
    from app.services.voyage_schedule_service import build_voyage_schedule

    try:
        case = get_case(case_id)
    except KeyError:
        return []
    schedule = build_voyage_schedule(case)
    positions = schedule.get("positions", [])
    events: list[dict] = []
    now = datetime.now(UTC)

    for storm in storms:
        hits = []
        for position in positions:
            transit_moment = datetime.fromisoformat(position["date"] + "T12:00:00+00:00")
            storm_position = _storm_position_at(storm, transit_moment)
            if storm_position is None:
                continue
            lead_days = max(0.0, (transit_moment - now).total_seconds() / 86400)
            cone_radius = CONE_BASE_RADIUS_KM + CONE_GROWTH_KM_PER_DAY * lead_days
            distance = _distance_km(position["lat"], position["lng"], storm_position["lat"], storm_position["lng"])
            if distance <= cone_radius:
                hits.append({"position": position, "storm_position": storm_position, "distance_km": round(distance), "cone_radius_km": round(cone_radius), "lead_days": round(lead_days, 1)})
        if hits:
            events.append(_route_crossing_event(case_id, case, storm, hits, now))

        pol_event = _pol_threat_event(case_id, case, storm, now)
        if pol_event:
            events.append(pol_event)

    return events


def _route_crossing_event(case_id: str, case: dict, storm: dict, hits: list[dict], now: datetime) -> dict:
    first, last = hits[0], hits[-1]
    max_wind = max(point["max_wind_kt"] for point in storm["points"])
    severity = "CRITICAL" if max_wind >= 85 else ("HIGH" if max_wind >= 64 else "MEDIUM")
    region = first["position"]["region"]
    window = {"start": first["position"]["date"], "end": last["position"]["date"], "basis": "typhoon_forecast"}
    return {
        "event_id": f"EVT-TC-{abs(hash((storm['storm_id'], case_id, window['start']))) % 1000000:06d}",
        "source": "typhoon_track_connector",
        "source_type": "WEATHER",
        "event_type": "WEATHER",
        "title": f"Typhoon {storm['name']} forecast track crosses route near {region} around {first['position']['date']}",
        "description": (
            f"Forecast cone of typhoon {storm['name']} intersects the planned route where the vessel is expected "
            f"between {window['start']} and {window['end']} (closest pass ~{first['distance_km']} km, cone radius {first['cone_radius_km']} km)."
        ),
        "event_time": window["start"],
        "published_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "locations": [region],
        "affected_ports": [],
        "affected_routes": [region],
        "affected_vessels": [case.get("vessel")] if case.get("vessel") else [],
        "affected_region": region,
        "severity": severity,
        "confidence": 0.9,
        "voyage_aligned": True,
        "expected_impact_window": window,
        "url": None,
        "raw_payload": {
            "storm": _storm_payload(storm, now),
            "hits": hits,
        },
        "dedup_key": f"TYPHOON|{storm['storm_id']}|{case_id}|{window['start']}",
        "impact": f"Typhoon {storm['name']} may force rerouting or delay on the {region} leg; departure delay and ETA impact possible.",
    }


def _pol_threat_event(case_id: str, case: dict, storm: dict, now: datetime) -> dict | None:
    from app.services.port_registry_service import resolve_port

    pol = resolve_port(case.get("port_of_loading"))
    etd = _parse_date(case.get("etd"))
    if not pol or not etd:
        return None
    threat = None
    for point in storm["points"]:
        point_date = point["time"].date()
        if abs((point_date - etd).days) > 3:
            continue
        distance = _distance_km(pol["lat"], pol["lng"], point["lat"], point["lng"])
        lead_days = max(0.0, (point["time"] - now).total_seconds() / 86400)
        cone_radius = CONE_BASE_RADIUS_KM + CONE_GROWTH_KM_PER_DAY * lead_days
        if distance <= max(POL_PROXIMITY_KM, cone_radius):
            if threat is None or distance < threat["distance_km"]:
                threat = {"date": point_date.isoformat(), "distance_km": round(distance), "cone_radius_km": round(cone_radius)}
    if threat is None:
        return None
    max_wind = max(point["max_wind_kt"] for point in storm["points"])
    return {
        "event_id": f"EVT-TC-POL-{abs(hash((storm['storm_id'], case_id, threat['date']))) % 1000000:06d}",
        "source": "typhoon_track_connector",
        "source_type": "WEATHER",
        "event_type": "WEATHER",
        "title": f"Typhoon {storm['name']} forecast near {case.get('port_of_loading')} around planned ETD",
        "description": (
            f"Typhoon {storm['name']} is forecast within ~{threat['distance_km']} km of {case.get('port_of_loading')} "
            f"around {threat['date']}, inside the ETD window; loading and departure are at risk."
        ),
        "event_time": threat["date"],
        "published_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "locations": [case.get("port_of_loading")],
        "affected_ports": [case.get("port_of_loading")],
        "affected_routes": [],
        "affected_vessels": [],
        "affected_region": pol["region"],
        "severity": "CRITICAL" if max_wind >= 85 else "HIGH",
        "confidence": 0.9,
        "voyage_aligned": True,
        "expected_impact_window": {"start": threat["date"], "end": threat["date"], "basis": "typhoon_forecast"},
        "url": None,
        "raw_payload": {"storm": _storm_payload(storm, now), "pol_threat": threat},
        "dedup_key": f"TYPHOON_POL|{storm['storm_id']}|{case_id}",
        "impact": f"Potential departure delay at {case.get('port_of_loading')}; latest shipment date may be threatened.",
    }


def _storm_payload(storm: dict, now: datetime) -> dict:
    points = []
    for point in storm["points"]:
        lead_days = max(0.0, (point["time"] - now).total_seconds() / 86400)
        points.append({
            "time": point["time"].isoformat(timespec="seconds").replace("+00:00", "Z"),
            "lat": point["lat"],
            "lng": point["lng"],
            "max_wind_kt": point["max_wind_kt"],
            "cone_radius_km": round(CONE_BASE_RADIUS_KM + CONE_GROWTH_KM_PER_DAY * lead_days),
        })
    return {"storm_id": storm["storm_id"], "name": storm["name"], "points": points}


def _storm_position_at(storm: dict, moment: datetime) -> dict | None:
    points = storm["points"]
    if moment < points[0]["time"] or moment > points[-1]["time"]:
        return None
    for index in range(1, len(points)):
        if points[index]["time"] >= moment:
            before, after = points[index - 1], points[index]
            span = (after["time"] - before["time"]).total_seconds() or 1.0
            ratio = (moment - before["time"]).total_seconds() / span
            return {
                "lat": before["lat"] + ratio * (after["lat"] - before["lat"]),
                "lng": before["lng"] + ratio * (after["lng"] - before["lng"]),
            }
    return None


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    a, b = math.radians(lat1), math.radians(lat2)
    dlat = b - a
    dlng = math.radians(lng2 - lng1)
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
