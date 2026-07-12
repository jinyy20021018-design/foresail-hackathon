from datetime import datetime
import re

ALLOWED_FIELDS = {
    "buyer",
    "seller",
    "commodity",
    "quantity",
    "quantity_unit",
    "amount",
    "currency",
    "incoterm",
    "incoterm_named_place",
    "payment_method",
    "vessel",
    "route",
    "port_of_loading",
    "port_of_discharge",
    "final_destination",
    "etd",
    "eta",
    "latest_shipment_date",
    "lc_expiry_date",
    "presentation_period_days",
    "booking_reference",
    "lc_number",
    "issuing_bank",
    "beneficiary",
    "applicant",
    "shipper",
    "consignee",
    "insurance_policy_number",
    "coverage_type",
    "case_name",
}

DATE_FIELDS = {"etd", "eta", "latest_shipment_date", "lc_expiry_date"}


def validate_extracted_fields(items: list[dict] | None, document: dict) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    valid: list[dict] = []
    if not isinstance(items, list):
        return [], ["LLM output did not contain a fields array."]

    has_quantity_unit = any(
        isinstance(item, dict) and str(item.get("field_name") or "").strip() == "quantity_unit"
        for item in items
    )
    for item in items:
        if not isinstance(item, dict):
            warnings.append("Skipped non-object field item.")
            continue
        field_name = str(item.get("field_name") or "").strip()
        value = item.get("value")
        if field_name not in ALLOWED_FIELDS:
            warnings.append(f"Skipped unsupported field: {field_name or 'UNKNOWN'}.")
            continue
        if value in {None, ""}:
            warnings.append(f"Skipped empty field: {field_name}.")
            continue
        if field_name == "quantity":
            quantity_value, quantity_unit = _split_quantity(value)
            if quantity_value is None:
                warnings.append(f"Skipped invalid quantity value: {value}.")
                continue
            item = dict(item)
            item["value"] = quantity_value
            value = quantity_value
            if quantity_unit and not has_quantity_unit:
                unit_item = dict(item)
                unit_item["field_name"] = "quantity_unit"
                unit_item["value"] = quantity_unit
                items.append(unit_item)
                has_quantity_unit = True
        if field_name == "amount":
            amount_value = _normalize_amount(str(value))
            if amount_value is None:
                warnings.append(f"Skipped non-money amount value: {value}.")
                continue
            item = dict(item)
            item["value"] = amount_value
            value = amount_value

        confidence = _confidence(item.get("confidence"))
        evidence = str(item.get("evidence_text") or item.get("evidence") or "").strip()
        if not evidence:
            confidence = min(confidence, 0.65)
            warnings.append(f"Evidence missing for {field_name}; confidence was capped.")
        if field_name in DATE_FIELDS and not _date_like(str(value)):
            warnings.append(f"Date parse warning for {field_name}: {value}.")

        valid.append({
            "field_name": field_name,
            "value": value,
            "evidence_text": evidence or f"Extracted {field_name}: {value}",
            "confidence": confidence,
            "source_document": document.get("filename"),
        })
    return valid, warnings


def _confidence(value) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.75


def _date_like(value: str) -> bool:
    if not value:
        return False
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            pass
    return False


def _normalize_amount(value: str) -> int | float | None:
    normalized = value.strip().replace(",", "")
    lowered = normalized.lower()
    if any(unit in lowered for unit in [" ton", "tons", "mt", "kg", "metric", "unit", "units"]):
        return None
    cleaned = re.sub(r"\b(?:USD|EUR|CNY|SGD|GBP)\b|US\$|\$", "", normalized, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    if not cleaned or not all(char.isdigit() or char in ". " for char in cleaned):
        return None
    number = float(cleaned)
    return int(number) if number.is_integer() else number


def _split_quantity(value) -> tuple[int | float | None, str]:
    if isinstance(value, int | float):
        return value, ""
    text = str(value).strip()
    match = re.match(r"^([0-9][0-9,]*(?:\.[0-9]+)?)\s*(.*)$", text)
    if not match:
        return None, ""
    number_text, unit = match.groups()
    number = float(number_text.replace(",", ""))
    value_out = int(number) if number.is_integer() else number
    return value_out, unit.strip(" .,\r\n")
