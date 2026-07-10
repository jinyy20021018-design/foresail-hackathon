import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
UTC = timezone.utc

from app.services.port_geo_service import resolve_location_coordinates
from app.services.port_registry_service import resolve_port


class OpenMeteoWeatherConnector:
    name = "open_meteo_weather_connector"

    def __init__(self) -> None:
        self.last_result: dict = {}

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        locations = _watch_locations(watch_profile)
        if os.getenv("OPEN_METEO_ENABLED", "true").lower() != "true":
            self.last_result = _summary(locations, warnings=["Open-Meteo connector disabled."], enabled=False)
            return []

        events: list[dict] = []
        connector_errors: list[dict] = []
        warnings: list[str] = []
        checked = 0
        for location in locations:
            coordinates = resolve_location_coordinates(location)
            if not coordinates:
                warnings.append(f"LOCATION_COORDINATES_NOT_FOUND: {location}")
                continue
            checked += 1
            try:
                forecast = _fetch_forecast(coordinates)
                events.extend(_events_from_forecast(location, coordinates, forecast, watch_profile))
            except Exception as error:
                connector_errors.append({"location": location, "error": str(error)})

        voyage_positions = _voyage_positions_within_horizon(case_id)
        for position in voyage_positions:
            checked += 1
            try:
                forecast = _fetch_forecast({"lat": position["lat"], "lon": position["lng"]})
                voyage_event = _voyage_aligned_event(position, forecast, watch_profile)
                if voyage_event:
                    events.append(voyage_event)
            except Exception as error:
                connector_errors.append({"location": f"voyage@{position['date']}", "error": str(error)})

        self.last_result = {
            "enabled": True,
            "locations_checked": checked,
            "voyage_positions_checked": len(voyage_positions),
            "weather_events_extracted": len(events),
            "connector_errors": connector_errors,
            "warnings": list(dict.fromkeys(warnings)),
            "locations": locations,
        }
        return events


def _fetch_forecast(coordinates: dict) -> dict:
    base_url = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")
    params = {
        "latitude": coordinates["lat"],
        "longitude": coordinates["lon"],
        "hourly": "weather_code,precipitation,wind_speed_10m,wind_gusts_10m",
        "forecast_days": min(16, _int_env("OPEN_METEO_FORECAST_DAYS", 16)),
        "timezone": "UTC",
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "ForeSail-MVP/3.1"})
    with urllib.request.urlopen(request, timeout=_int_env("OPEN_METEO_TIMEOUT_SECONDS", 10)) as response:
        import json

        return json.loads(response.read().decode("utf-8"))


def _events_from_forecast(location: str, coordinates: dict, forecast: dict, watch_profile: dict) -> list[dict]:
    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    precipitation = hourly.get("precipitation") or []
    gusts = hourly.get("wind_gusts_10m") or []
    codes = hourly.get("weather_code") or []
    candidates: list[dict] = []
    for index, event_time in enumerate(times):
        precip = _number_at(precipitation, index)
        gust = _number_at(gusts, index)
        code = int(_number_at(codes, index) or 0)
        severity, reason = _weather_signal(precip, gust, code)
        if not severity:
            continue
        candidates.append(_weather_event(location, coordinates, event_time, severity, reason, precip, gust, code, watch_profile))
    return _aggregate_weather_events(candidates)


def _weather_signal(precip: float, gust: float, code: int) -> tuple[str | None, str | None]:
    if gust >= 60:
        return "HIGH", "wind gusts above 60 km/h"
    if precip >= 20:
        return "HIGH", "heavy precipitation above 20 mm/hour"
    if code in {95, 96, 99}:
        return "HIGH", "thunderstorm or severe weather code"
    if gust >= 40:
        return "MEDIUM", "wind gusts above 40 km/h"
    if precip >= 10:
        return "MEDIUM", "precipitation above 10 mm/hour"
    if code in {80, 81, 82}:
        return "MEDIUM", "rain shower weather code"
    return None, None


def _weather_event(location: str, coordinates: dict, event_time: str, severity: str, reason: str, precip: float, gust: float, code: int, watch_profile: dict) -> dict:
    country = coordinates.get("country")
    location_label = f"{location}, {country}" if country else location
    title_prefix = "High weather risk" if severity == "HIGH" else "Watch weather risk"
    affected_ports = [location] if location in (watch_profile.get("watched_ports") or []) else []
    affected_routes = [location] if location in (watch_profile.get("watched_route_regions") or []) else []
    port_record = resolve_port(location)
    affected_region = port_record["region"] if port_record else location
    return {
        "event_id": f"EVT-METEO-{abs(hash((location, severity, reason, event_time))) % 1000000:06d}",
        "source": "open_meteo_weather_connector",
        "source_type": "WEATHER",
        "event_type": "WEATHER",
        "title": f"{title_prefix} near {location_label}: {reason}",
        "description": f"Open-Meteo forecast indicates {reason} near {location_label}.",
        "event_time": event_time,
        "published_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "locations": [location],
        "affected_ports": affected_ports,
        "affected_routes": affected_routes,
        "affected_vessels": [],
        "affected_region": affected_region,
        "severity": severity,
        "confidence": 0.75 if severity == "HIGH" else 0.62,
        "url": None,
        "raw_payload": {"precipitation": precip, "wind_gusts_10m": gust, "weather_code": code, "coordinates": coordinates},
        "dedup_key": f"OPEN_METEO|WEATHER|{location.lower()}|{severity}|{reason}",
        "impact": f"Forecast weather condition may affect operations near {location_label}.",
    }


def _aggregate_weather_events(events: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for event in events:
        grouped.setdefault(event["dedup_key"], []).append(event)
    aggregated: list[dict] = []
    for dedup_key, group in grouped.items():
        best = max(group, key=lambda item: (item.get("confidence") or 0, _severity_rank(item.get("severity"))))
        first_time = min(str(item.get("event_time") or "") for item in group)
        last_time = max(str(item.get("event_time") or "") for item in group)
        output = dict(best)
        output["event_id"] = f"EVT-METEO-{abs(hash(dedup_key)) % 1000000:06d}"
        output["expected_impact_window"] = {"start": first_time, "end": last_time, "basis": "forecast"}
        output["description"] = f"{best['description']} Signal appears across {len(group)} forecast hour(s) from {first_time} to {last_time}."
        output["raw_payload"] = {**(best.get("raw_payload") or {}), "aggregated_hour_count": len(group), "first_event_time": first_time, "last_event_time": last_time}
        aggregated.append(output)
    aggregated.sort(key=lambda item: (_severity_rank(item.get("severity")), item.get("confidence") or 0), reverse=True)
    per_location: dict[str, int] = {}
    limited: list[dict] = []
    for event in aggregated:
        location = (event.get("locations") or [""])[0]
        if per_location.get(location, 0) >= 2:
            continue
        per_location[location] = per_location.get(location, 0) + 1
        limited.append(event)
    return limited


def _voyage_positions_within_horizon(case_id: str) -> list[dict]:
    from app.services.case_service import get_case
    from app.services.voyage_schedule_service import build_voyage_schedule

    try:
        case = get_case(case_id)
    except KeyError:
        return []
    schedule = build_voyage_schedule(case)
    today = date.today()
    horizon = today + timedelta(days=min(16, _int_env("OPEN_METEO_FORECAST_DAYS", 16)))
    upcoming = [
        position
        for position in schedule.get("positions", [])
        if today <= date.fromisoformat(position["date"]) <= horizon
    ]
    limit = _int_env("OPEN_METEO_VOYAGE_SAMPLE_LIMIT", 6)
    return upcoming[::2][:limit] if limit > 0 else upcoming[::2]


def _voyage_aligned_event(position: dict, forecast: dict, watch_profile: dict) -> dict | None:
    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    precipitation = hourly.get("precipitation") or []
    gusts = hourly.get("wind_gusts_10m") or []
    codes = hourly.get("weather_code") or []
    transit_date = date.fromisoformat(position["date"])
    window_start = (transit_date - timedelta(days=1)).isoformat()
    window_end = (transit_date + timedelta(days=1)).isoformat()

    worst: tuple[int, str, str] | None = None
    matched_times: list[str] = []
    for index, event_time in enumerate(times):
        if not (window_start <= str(event_time)[:10] <= window_end):
            continue
        severity, reason = _weather_signal(_number_at(precipitation, index), _number_at(gusts, index), int(_number_at(codes, index) or 0))
        if not severity:
            continue
        matched_times.append(str(event_time))
        rank = _severity_rank(severity)
        if worst is None or rank > worst[0]:
            worst = (rank, severity, reason)

    if worst is None:
        return None
    _, severity, reason = worst
    region = position["region"]
    return {
        "event_id": f"EVT-METEO-VOY-{abs(hash((position['date'], region, reason))) % 1000000:06d}",
        "source": "open_meteo_weather_connector",
        "source_type": "WEATHER",
        "event_type": "WEATHER",
        "title": f"Forecast weather risk on route near {region} around {position['date']}: {reason}",
        "description": (
            f"Open-Meteo forecast indicates {reason} near {region} in the window the vessel is expected to transit "
            f"(~{position['date']})."
        ),
        "event_time": matched_times[0],
        "published_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "locations": [region],
        "affected_ports": [],
        "affected_routes": [region],
        "affected_vessels": [],
        "affected_region": region,
        "severity": severity,
        "confidence": 0.75 if severity == "HIGH" else 0.62,
        "voyage_aligned": True,
        "expected_impact_window": {"start": min(matched_times)[:10], "end": max(matched_times)[:10], "basis": "forecast_voyage_aligned"},
        "url": None,
        "raw_payload": {"position": position, "matched_hours": len(matched_times)},
        "dedup_key": f"OPEN_METEO|WEATHER_VOYAGE|{region.lower()}|{position['date']}|{reason}",
        "impact": f"Forecast {reason} where the vessel is expected around {position['date']}; possible transit delay on this leg.",
    }


def _watch_locations(watch_profile: dict) -> list[str]:
    values = [*(watch_profile.get("watched_ports") or []), *(watch_profile.get("watched_route_regions") or [])]
    locations = list(dict.fromkeys(str(value) for value in values if value and str(value) != "TBD"))
    try:
        limit = int(os.getenv("REAL_EVENT_LOCATION_LIMIT", os.getenv("EXTERNAL_EVENT_QUERY_LIMIT", "3")))
    except ValueError:
        limit = 3
    return locations[:limit] if limit > 0 else locations


def _number_at(values: list, index: int) -> float:
    try:
        return float(values[index] or 0)
    except (IndexError, TypeError, ValueError):
        return 0.0


def _summary(locations: list[str], warnings: list[str], enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "locations_checked": 0,
        "weather_events_extracted": 0,
        "connector_errors": [],
        "warnings": warnings,
        "locations": locations,
    }


def _severity_rank(severity: str | None) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(str(severity or "").upper(), 0)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
