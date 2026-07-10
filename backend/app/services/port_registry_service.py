import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict


class PortRecord(TypedDict):
    unlocode: str
    name: str
    aliases: list[str]
    lat: float
    lng: float
    region: str


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "port_registry.json"

REGION_COORDINATES: dict[str, tuple[float, float]] = {
    "East China Sea": (28.0, 125.0),
    "South China Sea": (14.0, 115.0),
    "Yellow Sea": (35.0, 123.0),
    "Taiwan Strait": (24.5, 119.0),
    "Malacca Strait": (2.5, 101.5),
    "Java Sea": (-5.0, 110.0),
    "Bay of Bengal": (15.0, 88.0),
    "Bangladesh": (23.5, 90.5),
    "Indian Ocean": (5.0, 75.0),
    "Arabian Sea": (18.0, 65.0),
    "Persian Gulf": (26.0, 52.0),
    "Strait of Hormuz": (26.5, 56.5),
    "Red Sea": (20.0, 38.5),
    "Suez Canal": (30.0, 32.3),
    "Mediterranean": (36.0, 15.0),
    "North Sea": (54.0, 3.0),
    "Europe": (52.0, 5.0),
    "Pacific US": (34.0, -120.0),
    "US East Coast": (39.0, -74.0),
    "Korea Strait": (34.5, 129.0),
    "Northwest Pacific": (35.0, 140.0),
    "South Pacific": (-30.0, 150.0),
    "South Atlantic": (-25.0, -40.0),
    "Panama Canal": (9.0, -79.5),
}


@lru_cache(maxsize=1)
def load_port_registry() -> list[PortRecord]:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


EXTENDED_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "port_registry_extended.json"


@lru_cache(maxsize=1)
def load_extended_port_registry() -> list[dict]:
    if not EXTENDED_DATA_PATH.exists():
        return []
    with EXTENDED_DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _extended_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for record in load_extended_port_registry():
        keys = [
            str(record.get("unlocode") or "").lower(),
            str(record.get("name") or "").lower(),
            *[str(alias).lower() for alias in record.get("aliases") or []],
        ]
        for key in keys:
            if key:
                index.setdefault(key, record)
    return index


def _resolve_extended(name: str) -> dict | None:
    normalized = name.strip().lower()
    candidates = [
        normalized,
        normalized.replace("port of ", "").strip(),
        normalized.split(",")[0].strip(),
    ]
    index = _extended_index()
    for candidate in candidates:
        record = index.get(candidate)
        if record:
            return record
    return None


def normalize_port_key(name: str) -> str:
    value = name.strip().lower()
    aliases = {
        "shanghai": "shanghai",
        "chittagong": "chittagong",
        "chattogram": "chittagong",
        "long beach": "los-angeles",
    }
    for needle, normalized in aliases.items():
        if needle in value:
            return normalized
    return value.replace("port of ", "").replace(" ", "-")


def resolve_port(name: str | None) -> PortRecord | None:
    if not name or not name.strip() or name.strip().upper() == "TBD":
        return None

    normalized = name.strip().lower()
    best: PortRecord | None = None
    best_score = 0

    for record in load_port_registry():
        candidates = [record["name"].lower(), *[alias.lower() for alias in record["aliases"]]]
        for candidate in candidates:
            if normalized == candidate:
                return record
            if candidate in normalized or normalized in candidate:
                score = len(candidate)
                if score > best_score:
                    best = record
                    best_score = score

    return best or _resolve_extended(name)


def resolve_region_coordinates(region: str | None) -> tuple[float, float] | None:
    if not region:
        return None
    normalized = region.strip().lower()
    for key, coordinates in REGION_COORDINATES.items():
        if key.lower() in normalized or normalized in key.lower():
            return coordinates
    return None


def port_to_dict(record: PortRecord, input_name: str | None = None) -> dict:
    return {
        "name": input_name or record["name"],
        "display_name": record["name"],
        "unlocode": record["unlocode"],
        "lat": record["lat"],
        "lng": record["lng"],
        "region": record["region"],
    }
