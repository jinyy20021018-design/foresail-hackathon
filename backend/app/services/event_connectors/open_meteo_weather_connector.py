import json
import os
import urllib.parse
import urllib.request

from app.services.port_geo_service import resolve_location_coordinates


class OpenMeteoWeatherConnector:
    name = "open_meteo_weather_connector"

    def __init__(self) -> None:
        self.last_result: dict = {}

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        locations = _watch_locations(watch_profile)
        if os.getenv("OPEN_METEO_ENABLED", "false").lower() != "true":
            self.last_result = _summary(locations, warnings=["Open-Meteo connector disabled."], enabled=False)
            return []

        events: list[dict] = []
        connector_errors: list[dict] = []
        checked = 0
        unresolved: list[str] = []
        for location in locations:
            coordinate = resolve_location_coordinates(location)
            if not coordinate:
                unresolved.append(location)
                continue
            checked += 1
            try:
                forecast = _fetch_forecast(coordinate)
                events.extend(_events_from_forecast(location, coordinate, forecast))
            except Exception as error:
                connector_errors.append({"location": location, "error": str(error)})

        warnings = []
        if unresolved:
            warnings.append(f"LOCATION_COORDINATES_NOT_FOUND: {', '.join(unresolved)}")
        self.last_result = {
            "enabled": True,
            "locations_checked": checked,
            "weather_events_extracted": len(events),
            "connector_errors": connector_errors,
            "warnings": warnings,
            "locations": locations,
        }
        return events


def _fetch_forecast(coordinate: dict) -> dict:
    base_url = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")
    params = {
        "latitude": coordinate["lat"],
        "longitude": coordinate["lon"],
        "hourly": "weather_code,precipitation,wind_speed_10m,wind_gusts_10m",
        "forecast_days": _int_env("OPEN_METEO_FORECAST_DAYS", 3),
        "timezone": "UTC",
    }
    request = urllib.request.Request(f"{base_url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "ForeSail-MVP/3.1"})
    with urllib.request.urlopen(request, timeout=_int_env("OPEN_METEO_TIMEOUT_SECONDS", 10)) as response:
        return json.loads(response.read().decode("utf-8"))


def _events_from_forecast(location: str, coordinate: dict, forecast: dict) -> list[dict]:
    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    precipitation = hourly.get("precipitation") or []
    gusts = hourly.get("wind_gusts_10m") or []
    codes = hourly.get("weather_code") or []
    events: list[dict] = []
    for index, event_time in enumerate(times):
        precip = _value_at(precipitation, index)
        gust = _value_at(gusts, index)
        code = _value_at(codes, index)
        severity, reason = _weather_severity(precip, gust, code)
        if not severity:
            continue
        title = _weather_title(location, reason, severity)
        events.append({
            "event_id": f"EVT-METEO-{abs(hash((location, event_time, reason))) % 1000000:06d}",
            "source": "open_meteo_weather_connector",
            "source_type": "WEATHER",
            "event_type": "WEATHER",
            "title": title,
            "description": f"Forecast indicates {reason} near {location}.",
            "event_time": _iso_time(event_time),
            "published_at": None,
            "locations": [location],
            "affected_ports": [location] if coordinate.get("country") else [],
            "affected_routes": [location],
            "affected_vessels": [],
            "affected_region": location,
            "severity": severity,
            "confidence": 0.75 if severity == "HIGH" else 0.62,
            "url": None,
            "raw_payload": {"location": location, "coordinate": coordinate, "precipitation": precip, "wind_gusts_10m": gust, "weather_code": code},
            "dedup_key": f"OPEN_METEO|WEATHER|{location.lower()}|{event_time}|{reason}",
            "impact": f"Potential weather disruption near {location}.",
        })
    return events[:3]


def _weather_severity(precip, gust, code) -> tuple[str | None, str | None]:
    if gust is not None and float(gust) >= 60:
        return "HIGH", "high wind gusts above 60 km/h"
    if precip is not None and float(precip) >= 20:
        return "HIGH", "heavy precipitation above 20 mm/hour"
    if code in {95, 96, 99}:
        return "HIGH", "thunderstorm or severe weather code"
    if gust is not None and float(gust) >= 40:
        return "MEDIUM", "wind gusts above 40 km/h"
    if precip is not None and float(precip) >= 10:
        return "MEDIUM", "precipitation above 10 mm/hour"
    if code in {80, 81, 82}:
        return "MEDIUM", "rain shower weather code"
    return None, None


def _watch_locations(watch_profile: dict) -> list[str]:
    values = [
        *watch_profile.get("watched_ports", []),
        *watch_profile.get("watched_route_regions", []),
    ]
    return list(dict.fromkeys(str(value) for value in values if value and str(value) != "TBD"))


def _value_at(values: list, index: int):
    return values[index] if index < len(values) else None


def _weather_title(location: str, reason: str, severity: str) -> str:
    prefix = "High" if severity == "HIGH" else "Watch"
    return f"{prefix} weather risk near {location}: {reason}"


def _iso_time(value) -> str | None:
    if value in {None, ""}:
        return None
    text = str(value)
    return text if "T" in text else f"{text}T00:00:00Z"


def _summary(locations: list[str], warnings: list[str], enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "locations_checked": 0,
        "weather_events_extracted": 0,
        "connector_errors": [],
        "warnings": warnings,
        "locations": locations,
    }


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
