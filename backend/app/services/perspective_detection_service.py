import json
import os
import re
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "our_company.json"

ROLE_VOTES = {
    "beneficiary": "SELLER",
    "seller": "SELLER",
    "shipper": "SELLER",
    "applicant": "BUYER",
    "buyer": "BUYER",
    "consignee": "BUYER",
}

ROLE_LABELS = {
    "beneficiary": "LC Beneficiary",
    "applicant": "LC Applicant",
    "seller": "Contract Seller",
    "buyer": "Contract Buyer",
    "shipper": "B/L Shipper",
    "consignee": "B/L Consignee",
}

ROLE_PRIORITY = ["beneficiary", "applicant", "seller", "buyer", "shipper", "consignee"]

_SUFFIX_TOKENS = {
    "co",
    "ltd",
    "limited",
    "inc",
    "corp",
    "corporation",
    "company",
    "group",
    "trading",
    "industrial",
    "import",
    "export",
    "pte",
    "gmbh",
    "有限公司",
}


@lru_cache(maxsize=1)
def load_our_company() -> dict:
    name = os.getenv("OUR_COMPANY_NAME", "").strip()
    aliases_raw = os.getenv("OUR_COMPANY_ALIASES", "").strip()
    if name:
        aliases = [alias.strip() for alias in aliases_raw.split(",") if alias.strip()]
        return {"name": name, "aliases": aliases}
    if not DATA_PATH.exists():
        return {"name": "", "aliases": []}
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_company(value: str) -> str:
    normalized = re.sub(r"[^\w一-鿿]+", " ", str(value).lower()).strip()
    tokens = normalized.split()
    while tokens and tokens[-1] in _SUFFIX_TOKENS:
        tokens.pop()
    return " ".join(tokens)


def _matches_our_company(value: str) -> tuple[bool, str]:
    candidate = _normalize_company(value)
    if not candidate:
        return False, ""
    profile = load_our_company()
    names = [profile.get("name") or "", *(profile.get("aliases") or [])]
    for name in names:
        normalized = _normalize_company(name)
        if not normalized:
            continue
        if candidate == normalized:
            return True, name
        if len(normalized) >= 4 and len(candidate) >= 4:
            if normalized in candidate or candidate in normalized:
                return True, name
    return False, ""


def detect_trade_perspective(fields: list[dict]) -> dict:
    votes = []
    matches = []
    for field in fields:
        field_name = str(field.get("field_name") or "")
        if field_name not in ROLE_VOTES:
            continue
        value = str(field.get("value") or "")
        matched, alias = _matches_our_company(value)
        vote = ROLE_VOTES[field_name] if matched else None
        votes.append({"field_name": field_name, "value": value, "vote": vote, "matched": matched})
        if matched:
            matches.append({"field": field, "alias": alias, "vote": ROLE_VOTES[field_name]})

    if not matches:
        first = fields[0] if fields else {}
        return {
            "perspective": "SELLER",
            "source": "DEFAULT",
            "confidence": 0.4,
            "basis": "No company profile match; defaulted to SELLER",
            "evidence_text": "No extracted party matched the company profile.",
            "source_document_id": first.get("source_document_id"),
            "source_document_name": first.get("source_document_name"),
            "votes": votes,
        }

    seat_votes = {match["vote"] for match in matches}
    matches.sort(key=lambda match: ROLE_PRIORITY.index(match["field"]["field_name"]))
    best = matches[0]
    role = best["field"]["field_name"]
    perspective = best["vote"]
    conflict = len(seat_votes) > 1
    confidence = 0.55 if conflict else 0.92
    basis = f"{ROLE_LABELS[role]} · {best['field'].get('value')}"
    evidence = str(best["field"].get("evidence_text") or best["field"].get("value") or "")
    note = f" — matched company profile alias '{best['alias']}' → {perspective} seat"
    if conflict:
        conflicting = sorted(ROLE_LABELS[m["field"]["field_name"]] for m in matches if m["vote"] != perspective)
        note += f"; conflicting match on {', '.join(conflicting)}"
    return {
        "perspective": perspective,
        "source": "AUTO_DETECTED",
        "confidence": confidence,
        "basis": basis,
        "evidence_text": evidence + note,
        "source_document_id": best["field"].get("source_document_id"),
        "source_document_name": best["field"].get("source_document_name"),
        "votes": votes,
    }
