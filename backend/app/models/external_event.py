from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
UTC = timezone.utc
from typing import Optional


@dataclass
class NormalizedExternalEvent:
    event_id: str
    source: str
    source_type: str
    event_type: str
    title: str
    description: str
    event_time: Optional[str] = None
    published_at: Optional[str] = None
    locations: list[str] = field(default_factory=list)
    affected_ports: list[str] = field(default_factory=list)
    affected_routes: list[str] = field(default_factory=list)
    affected_vessels: list[str] = field(default_factory=list)
    severity: str = "UNKNOWN"
    confidence: float = 0.0
    url: Optional[str] = None
    raw_payload: Optional[dict] = None
    dedup_key: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"))
    case_id: Optional[str] = None
    agent_run_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
