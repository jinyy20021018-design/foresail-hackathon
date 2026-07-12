import copy
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

_OFFSET_FIELDS = {
    "event_time": "event_time_offset_days",
    "old_eta": "old_eta_offset_days",
    "new_eta": "new_eta_offset_days",
}


def anchor_event_dates(events: list[dict]) -> list[dict]:
    """Shift any *_offset_days field to a date relative to today, so seeded
    demo events stay near-term regardless of when the demo is run."""
    today = datetime.now(UTC).date()
    anchored = []
    for event in events:
        item = copy.deepcopy(event)
        for field, offset_key in _OFFSET_FIELDS.items():
            offset = item.pop(offset_key, None)
            if offset is None:
                continue
            item[field] = (today + timedelta(days=int(offset))).isoformat()
        anchored.append(item)
    return anchored
