import os

VALID_EXTRACTION_MODES = {"AUTO", "TEXT_FIRST", "OPENAI_FILE", "VISION_PAGES", "FALLBACK_ONLY"}


def document_extraction_mode() -> str:
    mode = os.getenv("DOCUMENT_EXTRACTION_MODE", "AUTO").upper()
    return mode if mode in VALID_EXTRACTION_MODES else "AUTO"


def base_diagnostic(document: dict, mode: str) -> dict:
    return {
        "document_id": document["document_id"],
        "filename": document["filename"],
        "document_type": document.get("document_type", "UNKNOWN"),
        "extraction_mode": mode,
        "status": "FAILED",
        "text_extraction_status": "NOT_RUN",
        "pdf_type": None,
        "llm_used": False,
        "fallback_used": False,
        "vision_used": False,
        "openai_file_used": False,
        "fields_extracted_count": 0,
        "missing_fields": [],
        "warnings": [],
        "errors": [],
    }


def expected_fields_for_document_type(document_type: str) -> list[str]:
    if document_type == "LETTER_OF_CREDIT":
        return ["amount", "currency", "latest_shipment_date", "lc_expiry_date", "payment_method"]
    if document_type == "BOOKING_CONFIRMATION":
        return ["vessel", "port_of_loading", "port_of_discharge", "etd", "eta"]
    if document_type == "INSURANCE_CERTIFICATE":
        return ["insurance_policy_number", "coverage_type"]
    return ["buyer", "seller", "commodity", "amount", "currency", "incoterm", "payment_method"]


def finalize_diagnostic(diagnostic: dict, fields: list[dict]) -> dict:
    field_names = {field.get("field_name") for field in fields}
    field_values = {field.get("field_name"): field.get("value") for field in fields}
    expected = expected_fields_for_document_type(diagnostic.get("document_type", "UNKNOWN"))
    missing = [field for field in expected if field not in field_names]
    diagnostic["fields_extracted_count"] = len(fields)
    diagnostic["missing_fields"] = missing
    if str(field_values.get("incoterm") or "").upper() == "CIF" and "incoterm_named_place" not in field_names:
        diagnostic["warnings"].append("CIF_NAMED_DESTINATION_PORT_MISSING")
    if diagnostic["status"] in {"NEEDS_VISION", "UNSUPPORTED"}:
        return diagnostic
    if not fields and diagnostic["status"] not in {"NEEDS_VISION", "UNSUPPORTED"}:
        diagnostic["status"] = "FAILED"
        if not diagnostic["errors"]:
            diagnostic["errors"].append({
                "code": "NO_RELIABLE_FIELDS_EXTRACTED",
                "message": "No reliable fields were extracted from the uploaded document.",
            })
    elif missing:
        diagnostic["status"] = "PARTIAL"
    else:
        diagnostic["status"] = "SUCCESS"
    return diagnostic
