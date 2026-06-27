import os

from app.services.document_service import get_documents, get_extracted_fields, get_field_conflicts

AUTOFILL_FIELDS = [
    "case_name",
    "buyer",
    "seller",
    "commodity",
    "port_of_loading",
    "port_of_discharge",
    "final_destination",
    "owner",
    "notes",
]

EXTRA_FACT_FIELDS = [
    "vessel",
    "route",
    "quantity",
    "quantity_unit",
    "amount",
    "currency",
    "incoterm",
    "payment_method",
    "etd",
    "eta",
    "latest_shipment_date",
    "lc_expiry_date",
    "presentation_period_days",
]


def build_case_detail_autofill(case_id: str) -> dict:
    documents = get_documents(case_id)
    fields = get_extracted_fields(case_id)
    conflicts = get_field_conflicts(case_id)
    document_types = {document["document_id"]: document.get("document_type", "UNKNOWN") for document in documents}
    conflict_names = {conflict["field_name"] for conflict in conflicts if conflict.get("status") == "OPEN"}
    field_map = _select_fields(fields, document_types)
    document_diagnostics = [document.get("extraction_diagnostics") for document in documents if document.get("extraction_diagnostics")]

    if not field_map:
        return {
            "case_id": case_id,
            "status": "FAILED",
            "extraction_mode": _autofill_mode(document_diagnostics),
            "llm_used": any(item.get("llm_used") for item in document_diagnostics),
            "fallback_used": any(item.get("fallback_used") for item in document_diagnostics) or _fallback_used(),
            "autofill": {},
            "extra_facts": {},
            "field_sources": {},
            "conflicts": conflicts,
            "document_diagnostics": document_diagnostics,
            "warnings": _diagnostic_warnings(document_diagnostics),
            "errors": [{
                "code": "NO_RELIABLE_FIELDS_EXTRACTED",
                "message": "No reliable fields were extracted from the uploaded documents.",
            }],
            "document_processing_summary": f"Processed {len(documents)} documents and 0 extracted fields.",
        }

    values = {name: _field_value(field_map.get(name)) for name in AUTOFILL_FIELDS + EXTRA_FACT_FIELDS}
    autofill = {
        "case_name": values.get("case_name") or _case_name(values),
        "buyer": values.get("buyer") or "",
        "seller": values.get("seller") or "",
        "commodity": values.get("commodity") or "",
        "port_of_loading": values.get("port_of_loading") or "",
        "port_of_discharge": values.get("port_of_discharge") or "",
        "final_destination": values.get("final_destination") or "",
        "owner": "Trade Ops",
        "notes": "Created from uploaded trade documents. Extracted fields are pending human review.",
    }
    extra_facts = {name: values.get(name) for name in EXTRA_FACT_FIELDS if values.get(name) not in {None, ""}}
    warnings = []
    if _fallback_used():
        warnings.append("LLM extraction is unavailable. The system used fallback extraction.")
    if conflicts:
        warnings.append("Field conflicts detected. Review conflicts in the Case Workspace before confirming case facts.")
    missing = [name for name in ["buyer", "seller", "commodity", "port_of_loading", "port_of_discharge", "final_destination"] if not values.get(name)]
    if missing:
        warnings.append(f"Missing key fields: {', '.join(missing)}.")
    warnings.extend(_diagnostic_warnings(document_diagnostics))
    status = "SUCCESS" if not missing and fields else "PARTIAL"

    return {
        "case_id": case_id,
        "status": status,
        "extraction_mode": _autofill_mode(document_diagnostics),
        "llm_used": any(item.get("llm_used") for item in document_diagnostics) or not _fallback_used(),
        "fallback_used": any(item.get("fallback_used") for item in document_diagnostics) or _fallback_used(),
        "autofill": autofill,
        "extra_facts": extra_facts,
        "field_sources": _field_sources(field_map, conflict_names),
        "conflicts": conflicts,
        "document_diagnostics": document_diagnostics,
        "warnings": warnings,
        "errors": [],
        "document_processing_summary": f"Processed {len(documents)} documents and {len(fields)} extracted fields.",
    }


def _select_fields(fields: list[dict], document_types: dict[str, str]) -> dict[str, dict]:
    selected: dict[str, dict] = {}
    for field in fields:
        name = field["field_name"]
        current = selected.get(name)
        if current is None or _field_rank(field, document_types) > _field_rank(current, document_types):
            selected[name] = field
    return selected


def _field_rank(field: dict, document_types: dict[str, str]) -> tuple[int, float]:
    doc_type = document_types.get(field.get("source_document_id"), "UNKNOWN")
    priority = {
        "buyer": {"CONTRACT_PO": 10},
        "seller": {"CONTRACT_PO": 10},
        "commodity": {"CONTRACT_PO": 10},
        "quantity": {"CONTRACT_PO": 10},
        "quantity_unit": {"CONTRACT_PO": 10},
        "amount": {"LETTER_OF_CREDIT": 9, "CONTRACT_PO": 8},
        "currency": {"LETTER_OF_CREDIT": 9, "CONTRACT_PO": 8},
        "vessel": {"BOOKING_CONFIRMATION": 10},
        "etd": {"BOOKING_CONFIRMATION": 10},
        "eta": {"BOOKING_CONFIRMATION": 10},
        "latest_shipment_date": {"LETTER_OF_CREDIT": 10},
        "lc_expiry_date": {"LETTER_OF_CREDIT": 10},
        "presentation_period_days": {"LETTER_OF_CREDIT": 10},
        "port_of_loading": {"BOOKING_CONFIRMATION": 10, "CONTRACT_PO": 8},
        "port_of_discharge": {"BOOKING_CONFIRMATION": 10, "CONTRACT_PO": 8},
        "final_destination": {"CONTRACT_PO": 10, "BOOKING_CONFIRMATION": 8},
        "incoterm": {"CONTRACT_PO": 10},
        "payment_method": {"LETTER_OF_CREDIT": 10, "CONTRACT_PO": 8},
    }
    return (priority.get(field["field_name"], {}).get(doc_type, 0), float(field.get("confidence") or 0))


def _field_value(field: dict | None):
    if not field:
        return ""
    return field.get("edited_value") if field.get("review_status") == "EDITED" else field.get("value")


def _field_sources(field_map: dict[str, dict], conflict_names: set[str]) -> dict:
    sources = {}
    for name, field in field_map.items():
        sources[name] = {
            "source_document": field.get("source_document_name"),
            "confidence": field.get("confidence"),
            "evidence": field.get("evidence_text"),
            "review_status": field.get("review_status"),
            "conflict": name in conflict_names,
        }
    return sources


def _case_name(values: dict) -> str:
    if values.get("port_of_loading") and values.get("port_of_discharge") and values.get("commodity"):
        return f"{values['port_of_loading']} to {values['port_of_discharge']} {values['commodity']} Shipment"
    if values.get("vessel") and values.get("route"):
        return f"{values['vessel']} Trade Watch"
    if values.get("commodity"):
        return f"{values['commodity']} Trade Case"
    return "New Trade Case"


def _fallback_used() -> bool:
    return os.getenv("USE_LLM_EXTRACTION", "").lower() != "true" or not os.getenv("OPENAI_API_KEY")


def _autofill_mode(diagnostics: list[dict]) -> str:
    modes = [item.get("extraction_mode") for item in diagnostics if item.get("extraction_mode")]
    if not modes:
        return "FALLBACK" if _fallback_used() else "LLM"
    return modes[0] if len(set(modes)) == 1 else "MIXED"


def _diagnostic_warnings(diagnostics: list[dict]) -> list[str]:
    values: list[str] = []
    for item in diagnostics:
        values.extend(item.get("warnings") or [])
        for error in item.get("errors") or []:
            message = error.get("message")
            if message:
                values.append(message)
    return list(dict.fromkeys(values))
