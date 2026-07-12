import json
from pathlib import Path

from app.services.event_date_anchor import anchor_event_dates

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "curated_events.json"


class CuratedEventConnector:
    name = "curated_event_connector"

    def fetch_events(self, watch_profile: dict, case_id: str) -> list[dict]:
        if not DATA_PATH.exists():
            return []
        with DATA_PATH.open("r", encoding="utf-8") as handle:
            events = json.load(handle)
        return anchor_event_dates(events) if isinstance(events, list) else []
