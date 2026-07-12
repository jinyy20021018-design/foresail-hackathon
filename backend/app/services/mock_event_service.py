import json
from pathlib import Path

from app.services.event_date_anchor import anchor_event_dates

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def get_mock_events() -> list[dict]:
    with (DATA_DIR / "mock_events.json").open("r", encoding="utf-8") as file:
        events = json.load(file)
    return anchor_event_dates(events)
