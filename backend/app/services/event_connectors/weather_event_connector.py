import os
from datetime import datetime, timezone
UTC = timezone.utc


class WeatherEventConnector:
    name = "weather_event_connector"

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        if os.getenv("WEATHER_API_ENABLED", "false").lower() != "true":
            return []

        # MVP 3.0 does not depend on a specific paid weather provider. When a
        # project config enables this connector without wiring a provider yet,
        # return a clearly marked fallback observation instead of failing.
        watched_ports = _watch_ports(watch_profile)
        target = watched_ports[-1] if watched_ports else "Unknown"
        now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        return [
            {
                "source": "weather_connector_fallback",
                "source_type": "WEATHER",
                "event_type": "WEATHER",
                "title": f"Weather watch near {target}",
                "description": f"Weather connector fallback observation for {target}; no live provider response is configured.",
                "event_time": now[:10],
                "published_at": now,
                "locations": [target],
                "affected_ports": [target] if target != "Unknown" else [],
                "affected_routes": watch_profile.get("watched_route_regions", []),
                "affected_vessels": [],
                "affected_region": target,
                "severity": "LOW",
                "confidence": 0.45,
                "url": None,
                "raw_payload": {"fallback": True},
                "impact": "Fallback weather watch only; verify with an external weather source before action.",
            }
        ]


def _watch_ports(watch_profile: dict) -> list[str]:
    return [port for port in watch_profile.get("watched_ports", []) if port]
