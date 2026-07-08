import os
from datetime import datetime, timezone
UTC = timezone.utc


class NewsEventConnector:
    name = "news_event_connector"

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        if os.getenv("NEWS_API_ENABLED", "false").lower() != "true":
            return []

        feed_urls = [url.strip() for url in os.getenv("NEWS_FEED_URLS", "").split(",") if url.strip()]
        if not feed_urls:
            return []

        # MVP 3.0 provider-neutral fallback: do not make a network call here.
        # The connector proves configuration, keyword generation, normalization,
        # and graceful handling without binding the product to a paid API.
        keywords = _keywords(watch_profile)
        now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        return [
            {
                "source": "news_connector_configured",
                "source_type": "NEWS",
                "event_type": "PORT_DISRUPTION",
                "title": f"Configured news watch for {keywords[0] if keywords else 'trade route'}",
                "description": f"News connector is configured for keywords: {', '.join(keywords[:6])}. No live fetch is performed in MVP 3.0.",
                "event_time": now[:10],
                "published_at": now,
                "locations": keywords[:3],
                "affected_ports": watch_profile.get("watched_ports", []),
                "affected_routes": watch_profile.get("watched_route_regions", []),
                "affected_vessels": [watch_profile.get("watched_vessel")] if watch_profile.get("watched_vessel") else [],
                "affected_region": (watch_profile.get("watched_route_regions") or [""])[-1],
                "severity": "MEDIUM",
                "confidence": 0.5,
                "url": feed_urls[0],
                "raw_payload": {"feed_urls": feed_urls, "keywords": keywords, "fallback": True},
                "impact": "Configured news watch only; review source feed before action.",
            }
        ]


def _keywords(watch_profile: dict) -> list[str]:
    values = [
        watch_profile.get("watched_vessel"),
        *watch_profile.get("watched_ports", []),
        *watch_profile.get("watched_route_regions", []),
        "port strike",
        "port congestion",
        "shipping delay",
        "customs disruption",
    ]
    return [str(value) for value in values if value]
