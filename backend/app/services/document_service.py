import copy
import html
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
UTC = timezone.utc
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from app.services.case_service import get_case, replace_case_facts
from app.services.document_extraction_pipeline import base_diagnostic, document_extraction_mode, finalize_diagnostic
from app.services.extraction_schema_validator import validate_extracted_fields
from app.services.openai_file_extraction_service import extract_with_openai_file
from app.services.pdf_detection_service import detect_pdf, extract_pdf_text
from app.services.persistence_service import load_item, save_item, clear_namespace
from app.services.perspective_detection_service import detect_trade_perspective
from app.services.vision_pages_extraction_service import extract_with_vision_pages

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
UPLOAD_DIR.mkdir(exist_ok=True)

CRITICAL_FIELDS = {
    "vessel",
    "port_of_loading",
    "port_of_discharge",
    "etd",
    "eta",
    "latest_shipment_date",
    "payment_method",
    "incoterm",
    "amount",
    "currency",
}

_documents: dict[str, list[dict]] = {}
_fields: dict[str, list[dict]] = {}
_confirmed_facts: dict[str, dict] = {}
_obligations: dict[str, list[dict]] = {}
_information_gaps: dict[str, list[dict]] = {}
_action_drafts: dict[str, list[dict]] = {}
_field_conflicts: dict[str, list[dict]] = {}
_doc_counter = 1
_field_counter = 1


def reset_document_store() -> None:
    global _doc_counter, _field_counter
    clear_runtime_document_cache()
    if UPLOAD_DIR.exists():
        for child in UPLOAD_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    for namespace in [
        "documents",
        "extracted_fields",
        "confirmed_facts",
        "obligations",
        "information_gaps",
        "action_drafts",
        "field_conflicts",
        "agent_run",
        "agent_trace",
        "treatment_plan",
        "action_set",
        "plan_set",
        "residual_risk",
        "approval_package",
        "external_event",
    ]:
        clear_namespace(namespace)


def clear_runtime_document_cache() -> None:
    global _doc_counter, _field_counter
    _documents.clear()
    _fields.clear()
    _confirmed_facts.clear()
    _obligations.clear()
    _information_gaps.clear()
    _action_drafts.clear()
    _field_conflicts.clear()
    _doc_counter = 1
    _field_counter = 1


def clear_case_document_cache(case_id: str) -> None:
    _documents.pop(case_id, None)
    _fields.pop(case_id, None)
    _confirmed_facts.pop(case_id, None)
    _obligations.pop(case_id, None)
    _information_gaps.pop(case_id, None)
    _action_drafts.pop(case_id, None)
    _field_conflicts.pop(case_id, None)


def upload_document(case_id: str, filename: str, file: BinaryIO, document_type: str = "UNKNOWN") -> dict:
    global _doc_counter
    get_case(case_id)
    document_id = f"DOC-{_doc_counter:03d}"
    _doc_counter += 1

    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename)
    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(exist_ok=True)
    file_path = case_dir / f"{document_id}_{safe_name}"
    file_path.write_bytes(file.read())

    document = {
        "document_id": document_id,
        "case_id": case_id,
        "document_type": document_type if document_type != "UNKNOWN" else infer_document_type(filename, ""),
        "filename": filename,
        "file_path": str(file_path),
        "uploaded_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "parse_status": "UPLOADED",
        "extraction_status": "NOT_RUN",
        "extraction_mode": None,
        "pdf_type": None,
        "fields_extracted_count": 0,
        "extraction_diagnostics": None,
        "raw_text": "",
    }
    _documents.setdefault(case_id, []).append(document)
    _persist_documents(case_id)
    return copy.deepcopy(document)


def seed_demo_documents(case_id: str, conflict: bool = False, buyer: bool = False, hormuz: bool = False) -> dict:
    if hormuz:
        files = [
            ("contract.docx", "CONTRACT_PO", DATA_DIR / "demo_hormuz_contract.docx"),
            ("booking_confirmation.docx", "BOOKING_CONFIRMATION", DATA_DIR / "demo_hormuz_booking.docx"),
            ("letter_of_credit.docx", "LETTER_OF_CREDIT", DATA_DIR / "demo_hormuz_lc.docx"),
        ]
    elif buyer:
        files = [
            ("demo_contract.txt", "CONTRACT_PO", DATA_DIR / "demo_contract_buyer.txt"),
            ("demo_booking.txt", "BOOKING_CONFIRMATION", DATA_DIR / "demo_booking_buyer.txt"),
            ("demo_lc.txt", "LETTER_OF_CREDIT", DATA_DIR / "demo_lc_buyer.txt"),
        ]
    else:
        files = [
            ("demo_contract.txt", "CONTRACT_PO", DATA_DIR / "demo_contract_clean.txt"),
            ("demo_booking.txt", "BOOKING_CONFIRMATION", DATA_DIR / "demo_booking_clean.txt"),
            ("demo_lc.txt", "LETTER_OF_CREDIT", DATA_DIR / ("demo_lc_conflict.txt" if conflict else "demo_lc_clean.txt")),
        ]
    for filename, document_type, path in files:
        upload_document(case_id, filename, BytesIO(path.read_bytes()), document_type)
    return extract_documents(case_id)


def get_documents(case_id: str) -> list[dict]:
    get_case(case_id)
    if case_id not in _documents:
        _documents[case_id] = load_item("documents", case_id) or []
    return copy.deepcopy(_documents.get(case_id, []))


def extract_documents(case_id: str) -> dict:
    documents = get_documents(case_id)
    extracted: list[dict] = []
    parse_errors: list[dict] = []
    diagnostics: list[dict] = []

    for document in documents:
        diagnostic = base_diagnostic(document, document_extraction_mode())
        try:
            raw_text, diagnostic = extract_text_for_pipeline(Path(document["file_path"]), document, diagnostic)
            document["raw_text"] = raw_text
            document["document_type"] = infer_document_type(document["filename"], raw_text, document["document_type"])
            diagnostic["document_type"] = document["document_type"]
            fields = extract_fields_from_document(case_id, document, raw_text, diagnostic)
            diagnostic = finalize_diagnostic(diagnostic, fields)
            document["parse_status"] = "PARSED" if diagnostic["status"] in {"SUCCESS", "PARTIAL"} else "FAILED"
            document["extraction_status"] = diagnostic["status"]
            document["extraction_mode"] = diagnostic["extraction_mode"]
            document["pdf_type"] = diagnostic.get("pdf_type")
            document["fields_extracted_count"] = diagnostic["fields_extracted_count"]
            document["extraction_diagnostics"] = diagnostic
            extracted.extend(fields)
        except Exception as error:
            document["parse_status"] = "FAILED"
            diagnostic["status"] = "FAILED"
            diagnostic["errors"].append({"code": "EXTRACTION_FAILED", "message": str(error)})
            document["extraction_status"] = "FAILED"
            document["extraction_mode"] = diagnostic["extraction_mode"]
            document["pdf_type"] = diagnostic.get("pdf_type")
            document["fields_extracted_count"] = 0
            document["extraction_diagnostics"] = diagnostic
            parse_errors.append({"document_id": document["document_id"], "filename": document["filename"], "error": str(error)})
        diagnostics.append(document.get("extraction_diagnostics") or diagnostic)

    if extracted:
        extracted.append(_perspective_field(case_id, extracted))
    _documents[case_id] = documents
    _fields[case_id] = extracted
    detect_field_conflicts(case_id)
    _persist_documents(case_id)
    _persist_fields(case_id)
    _persist_conflicts(case_id)
    return {
        "documents": get_documents(case_id),
        "extracted_fields": get_extracted_fields(case_id),
        "parse_errors": parse_errors,
        "document_diagnostics": diagnostics,
        "status": _overall_extraction_status(diagnostics),
    }


def get_extracted_fields(case_id: str) -> list[dict]:
    get_case(case_id)
    if case_id not in _fields:
        _fields[case_id] = load_item("extracted_fields", case_id) or []
    return copy.deepcopy(_fields.get(case_id, []))


def approve_field(case_id: str, field_id: str) -> dict:
    field = _find_field(case_id, field_id)
    field["review_status"] = "APPROVED"
    _persist_fields(case_id)
    return copy.deepcopy(field)


def edit_field(case_id: str, field_id: str, value) -> dict:
    field = _find_field(case_id, field_id)
    field["edited_value"] = value
    field["review_status"] = "EDITED"
    detect_field_conflicts(case_id)
    _persist_fields(case_id)
    _persist_conflicts(case_id)
    return copy.deepcopy(field)


def reject_field(case_id: str, field_id: str) -> dict:
    field = _find_field(case_id, field_id)
    field["review_status"] = "REJECTED"
    detect_field_conflicts(case_id)
    _persist_fields(case_id)
    _persist_conflicts(case_id)
    return copy.deepcopy(field)


def confirm_fields(case_id: str) -> dict:
    high_conflicts = [conflict for conflict in get_field_conflicts(case_id) if conflict["severity"] == "High" and conflict["status"] == "OPEN"]
    if high_conflicts:
        raise ValueError("Unresolved high-severity field conflicts must be resolved before confirming fields.")

    fields = get_extracted_fields(case_id)
    facts = {}
    for field in fields:
        if field["review_status"] in {"APPROVED", "EDITED"}:
            facts[field["field_name"]] = field["edited_value"] if field["review_status"] == "EDITED" else field["value"]

    base_case = get_case(case_id)
    if not facts:
        facts = {field: base_case.get(field) for field in CRITICAL_FIELDS if base_case.get(field) not in {None, ""}}
        if facts.get("route") in {None, ""}:
            facts["route"] = base_case.get("route")
        if facts.get("final_destination") in {None, ""}:
            facts["final_destination"] = base_case.get("final_destination")

    missing = sorted(field for field in CRITICAL_FIELDS if facts.get(field) in {None, ""})
    if missing:
        raise ValueError(f"Missing confirmed critical fields: {', '.join(missing)}")

    perspective_value = ""
    perspective_source = str(base_case.get("perspective_source") or "DEFAULT")
    perspective_basis = str(base_case.get("perspective_basis") or "")
    perspective_field = next(
        (field for field in fields if field["field_name"] == "trade_perspective" and field["review_status"] in {"APPROVED", "EDITED"}),
        None,
    )
    if perspective_field:
        raw = perspective_field["edited_value"] if perspective_field["review_status"] == "EDITED" else perspective_field["value"]
        candidate = str(raw or "").strip().upper()
        if candidate in {"SELLER", "BUYER"}:
            perspective_value = candidate
            if perspective_field["review_status"] == "EDITED":
                perspective_source = "MANUAL"
                perspective_basis = "Edited during document review"
            else:
                perspective_source = str(perspective_field.get("detection_source") or "AUTO_DETECTED")
                perspective_basis = str(perspective_field.get("detection_basis") or "")
    if not perspective_value:
        perspective_value = str(base_case.get("trade_perspective") or "SELLER")

    confirmed = {
        "case_id": case_id,
        "vessel": str(facts["vessel"]),
        "route": str(facts.get("route") or base_case.get("route")),
        "port_of_loading": str(facts["port_of_loading"]),
        "port_of_discharge": str(facts["port_of_discharge"]),
        "final_destination": str(facts.get("final_destination") or base_case.get("final_destination")),
        "etd": str(facts["etd"]),
        "eta": str(facts["eta"]),
        "latest_shipment_date": str(facts["latest_shipment_date"]),
        "lc_expiry_date": str(facts.get("lc_expiry_date") or ""),
        "presentation_period_days": _int_or_none(facts.get("presentation_period_days")),
        "payment_method": str(facts["payment_method"]),
        "incoterm": str(facts["incoterm"]),
        "incoterm_named_place": str(facts.get("incoterm_named_place") or ""),
        "trade_perspective": perspective_value,
        "perspective_source": perspective_source,
        "perspective_basis": perspective_basis,
        "amount": _float_or_int(facts["amount"]),
        "currency": str(facts["currency"]),
        "booking_reference": facts.get("booking_reference"),
        "preliminary_assessment_notice": "Preliminary operational assessment only. Not legal, banking, or insurance advice.",
    }
    _confirmed_facts[case_id] = confirmed
    replace_case_facts(case_id, confirmed)
    save_item("confirmed_facts", case_id, confirmed, case_id)
    return copy.deepcopy(confirmed)


def get_confirmed_facts(case_id: str) -> dict:
    get_case(case_id)
    if case_id not in _confirmed_facts:
        stored = load_item("confirmed_facts", case_id)
        if stored:
            _confirmed_facts[case_id] = stored
    if case_id not in _confirmed_facts:
        raise KeyError(case_id)
    return copy.deepcopy(_confirmed_facts[case_id])


def sync_confirmed_perspective(case_id: str, perspective: str, source: str, basis: str) -> None:
    if case_id not in _confirmed_facts:
        stored = load_item("confirmed_facts", case_id)
        if stored:
            _confirmed_facts[case_id] = stored
    if case_id not in _confirmed_facts:
        return
    confirmed = _confirmed_facts[case_id]
    confirmed["trade_perspective"] = perspective
    confirmed["perspective_source"] = source
    confirmed["perspective_basis"] = basis
    save_item("confirmed_facts", case_id, confirmed, case_id)


def get_best_case_facts(case_id: str) -> dict:
    if case_id not in _confirmed_facts:
        stored = load_item("confirmed_facts", case_id)
        if stored:
            _confirmed_facts[case_id] = stored
    return copy.deepcopy(_confirmed_facts.get(case_id) or get_case(case_id))


def set_obligations(case_id: str, obligations: list[dict]) -> None:
    _obligations[case_id] = copy.deepcopy(obligations)
    save_item("obligations", case_id, obligations, case_id)


def get_obligations(case_id: str) -> list[dict]:
    get_case(case_id)
    if case_id not in _obligations:
        _obligations[case_id] = load_item("obligations", case_id) or []
    return copy.deepcopy(_obligations.get(case_id, []))


def set_information_gaps(case_id: str, gaps: list[dict]) -> None:
    _information_gaps[case_id] = copy.deepcopy(gaps)
    save_item("information_gaps", case_id, gaps, case_id)


def get_information_gaps(case_id: str) -> list[dict]:
    get_case(case_id)
    if case_id not in _information_gaps:
        _information_gaps[case_id] = load_item("information_gaps", case_id) or []
    return copy.deepcopy(_information_gaps.get(case_id, []))


def set_action_drafts(case_id: str, drafts: list[dict]) -> None:
    _action_drafts[case_id] = copy.deepcopy(drafts)
    save_item("action_drafts", case_id, drafts, case_id)


def get_action_drafts(case_id: str) -> list[dict]:
    get_case(case_id)
    if case_id not in _action_drafts:
        _action_drafts[case_id] = load_item("action_drafts", case_id) or []
    return copy.deepcopy(_action_drafts.get(case_id, []))


def regenerate_action_draft(case_id: str, draft_id: str) -> dict:
    for draft in _action_drafts.get(case_id, []):
        if draft["draft_id"] == draft_id:
            draft["body"] = draft["body"] + "\n\nRegenerated draft for user review."
            save_item("action_drafts", case_id, _action_drafts.get(case_id, []), case_id)
            return copy.deepcopy(draft)
    raise KeyError(draft_id)


def update_action_draft_status(case_id: str, draft_id: str, status: str, rejection_reason: str | None = None) -> dict:
    drafts = get_action_drafts(case_id)
    for draft in drafts:
        if draft["draft_id"] == draft_id:
            draft["status"] = status
            if rejection_reason:
                draft["rejection_reason"] = rejection_reason
            _action_drafts[case_id] = drafts
            save_item("action_drafts", case_id, drafts, case_id)
            return copy.deepcopy(draft)
    raise KeyError(draft_id)


def get_field_evidence(case_id: str, field_id: str) -> dict:
    field = _find_field(case_id, field_id)
    return {
        "field_name": field["field_name"],
        "display_name": field["display_name"],
        "value": field["edited_value"] if field["review_status"] == "EDITED" else field["value"],
        "source_document_id": field["source_document_id"],
        "source_document_name": field["source_document_name"],
        "page_number": field.get("page_number"),
        "evidence_text": field["evidence_text"],
        "confidence": field["confidence"],
        "review_status": field["review_status"],
    }


def get_field_conflicts(case_id: str) -> list[dict]:
    get_case(case_id)
    if case_id not in _field_conflicts:
        _field_conflicts[case_id] = load_item("field_conflicts", case_id) or []
    return copy.deepcopy(_field_conflicts.get(case_id, []))


def resolve_field_conflict(case_id: str, conflict_id: str, resolved_value, resolution_note: str, resolved_by: str) -> dict:
    conflicts = get_field_conflicts(case_id)
    for conflict in conflicts:
        if conflict["conflict_id"] == conflict_id:
            conflict["status"] = "RESOLVED"
            conflict["resolved_value"] = resolved_value
            conflict["resolution_note"] = resolution_note
            conflict["resolved_by"] = resolved_by
            _field_conflicts[case_id] = conflicts
            _persist_conflicts(case_id)
            return copy.deepcopy(conflict)
    raise KeyError(conflict_id)


def detect_field_conflicts(case_id: str) -> list[dict]:
    fields = _fields.get(case_id, load_item("extracted_fields", case_id) or [])
    conflicts: list[dict] = []

    def add_conflict(name: str, severity: str, values: list[dict], explanation: str, recommendation: str):
        if len({str(value["value"]).strip().lower() for value in values if value["value"] not in {None, ""}}) > 1:
            conflicts.append({
                "conflict_id": f"CONFLICT-{len(conflicts) + 1:03d}",
                "case_id": case_id,
                "field_name": name,
                "severity": severity,
                "status": "OPEN",
                "values": values,
                "explanation": explanation,
                "recommended_resolution": recommendation,
            })

    def values_for(name: str) -> list[dict]:
        return [
            {
                "value": field["edited_value"] if field["review_status"] == "EDITED" else field["value"],
                "source_document_name": field["source_document_name"],
                "source_document_type": _doc_type(case_id, field["source_document_id"]),
                "field_id": field["field_id"],
            }
            for field in fields
            if field["field_name"] == name and field["review_status"] != "REJECTED"
        ]

    amount_values = values_for("amount")
    add_conflict("amount", "High", amount_values, "The amount extracted from Contract / PO differs from the amount extracted from Letter of Credit.", "User must confirm the operative amount before running monitoring.")
    currency_values = values_for("currency")
    add_conflict("currency", "High", currency_values, "The currency extracted from Contract / PO differs from the currency extracted from Letter of Credit.", "User must confirm the operative currency before running monitoring.")
    destination_values = values_for("final_destination")
    add_conflict("final_destination", "Medium", destination_values, "The destination extracted across trade documents differs.", "User should confirm the operative destination.")
    incoterm_values = values_for("incoterm")
    add_conflict("incoterm", "Medium", incoterm_values, "The Incoterm extracted across trade documents differs.", "User should confirm the operative Incoterm.")

    previous = {conflict["conflict_id"]: conflict for conflict in _field_conflicts.get(case_id, [])}
    for conflict in conflicts:
        old = previous.get(conflict["conflict_id"])
        if old and old.get("status") == "RESOLVED":
            conflict.update({key: old.get(key) for key in ["status", "resolved_value", "resolution_note", "resolved_by"] if key in old})
    _field_conflicts[case_id] = conflicts
    return copy.deepcopy(conflicts)


def extract_text_for_pipeline(path: Path, document: dict, diagnostic: dict) -> tuple[str, dict]:
    mode = diagnostic["extraction_mode"]
    suffix = path.suffix.lower()
    if mode == "OPENAI_FILE":
        result = extract_with_openai_file(document)
        diagnostic.update({
            "status": result["status"],
            "openai_file_used": result.get("openai_file_used", False),
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
        })
        return "", diagnostic
    if suffix == ".pdf":
        pdf = detect_pdf(path)
        diagnostic["pdf_type"] = pdf["pdf_type"]
        diagnostic["warnings"].extend(pdf.get("warnings", []))
        if pdf["pdf_type"] == "TEXT_PDF" and mode in {"AUTO", "TEXT_FIRST", "FALLBACK_ONLY"}:
            diagnostic["text_extraction_status"] = "SUCCESS"
            return pdf["text"], diagnostic
        if pdf["pdf_type"] == "SCANNED_PDF":
            if mode in {"AUTO", "VISION_PAGES"}:
                vision = extract_with_vision_pages(document)
                diagnostic.update({
                    "status": vision["status"],
                    "vision_used": vision.get("vision_used", False),
                    "warnings": list(dict.fromkeys(diagnostic["warnings"] + vision.get("warnings", []))),
                    "errors": vision.get("errors", []),
                })
                diagnostic["text_extraction_status"] = "EMPTY_TEXT"
                return "", diagnostic
            diagnostic["text_extraction_status"] = "EMPTY_TEXT"
            diagnostic["status"] = "NEEDS_VISION"
            diagnostic["errors"].append({
                "code": "SCANNED_PDF_UNSUPPORTED",
                "message": "This PDF appears to be scanned. Enable VISION_PAGES extraction to process it.",
            })
            return "", diagnostic
        diagnostic["text_extraction_status"] = "FAILED"
        diagnostic["status"] = "FAILED"
        diagnostic["errors"].append({"code": "PDF_PARSE_FAILED", "message": "PDF text could not be reliably extracted."})
        return "", diagnostic
    if mode == "VISION_PAGES":
        vision = extract_with_vision_pages(document, reason_code="VISION_NOT_IMPLEMENTED")
        diagnostic.update({
            "status": vision["status"],
            "vision_used": vision.get("vision_used", False),
            "warnings": vision.get("warnings", []),
            "errors": vision.get("errors", []),
        })
        return "", diagnostic
    text = extract_text_from_file(path, document["filename"])
    diagnostic["text_extraction_status"] = "SUCCESS" if text.strip() else "EMPTY_TEXT"
    return text, diagnostic


def extract_text_from_file(path: Path, filename: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            xml_text = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        xml_text = re.sub(r"</w:p>", "\n", xml_text)
        return html.unescape(re.sub(r"<[^>]+>", " ", xml_text))
    if suffix == ".pdf":
        text = extract_pdf_text(path)
        if len(text.strip()) < 20:
            raise ValueError("PDF text extraction failed. Upload a text-based PDF or TXT/DOCX for MVP 2.0.")
        return text
    if suffix in {".png", ".jpg", ".jpeg"}:
        raise ValueError("OCR is not enabled in MVP 2.0. Upload TXT/DOCX or text-based PDF.")
    raise ValueError(f"Unsupported file type: {suffix}")


def infer_document_type(filename: str, raw_text: str, current: str = "UNKNOWN") -> str:
    if current and current != "UNKNOWN":
        return current
    value = f"{filename} {raw_text}".lower()
    if "letter of credit" in value or "latest shipment" in value or "issuing bank" in value:
        return "LETTER_OF_CREDIT"
    if "booking" in value or "vessel" in value or "eta" in value or "etd" in value:
        return "BOOKING_CONFIRMATION"
    if "contract" in value or "purchase order" in value or "incoterm" in value:
        return "CONTRACT_PO"
    return "UNKNOWN"


def extract_fields_from_document(case_id: str, document: dict, raw_text: str, diagnostic: dict | None = None) -> list[dict]:
    if not raw_text.strip():
        return []
    llm_fields = _try_llm_extraction(case_id, document, raw_text, diagnostic)
    if llm_fields is not None:
        return llm_fields

    doc_type = document["document_type"]
    if doc_type == "LETTER_OF_CREDIT":
        field_names = [
            "lc_number",
            "issuing_bank",
            "applicant",
            "beneficiary",
            "amount",
            "currency",
            "latest_shipment_date",
            "lc_expiry_date",
            "presentation_period_days",
            "partial_shipment_allowed",
            "transshipment_allowed",
            "payment_method",
        ]
    elif doc_type == "BOOKING_CONFIRMATION":
        field_names = [
            "vessel",
            "route",
            "port_of_loading",
            "port_of_discharge",
            "final_destination",
            "etd",
            "eta",
            "booking_reference",
            "shipper",
            "consignee",
        ]
    else:
        field_names = [
            "commodity",
            "quantity",
            "quantity_unit",
            "amount",
            "currency",
            "buyer",
            "seller",
            "incoterm",
            "incoterm_named_place",
            "payment_method",
            "final_destination",
        ]

    fields = []
    for name in field_names:
        value = _extract_value(name, raw_text, document)
        if value not in {None, ""}:
            fields.append(_make_field(case_id, document, name, value, raw_text))
    if diagnostic is not None:
        diagnostic["fallback_used"] = True
        if not fields:
            diagnostic["warnings"].append("Fallback parser did not find reliable fields.")
    return fields


def fallback_demo_fields(case_id: str, documents: list[dict]) -> list[dict]:
    fallback_document = documents[0] if documents else {
        "document_id": "DOC-FALLBACK",
        "filename": "fallback",
        "document_type": "FALLBACK",
    }
    values = {
        "vessel": "CAPEMOLLINI",
        "route": "Shanghai -> Chittagong -> Dhaka",
        "port_of_loading": "Shanghai",
        "port_of_discharge": "Chittagong",
        "final_destination": "Dhaka",
        "etd": "2026-11-25",
        "eta": "2026-12-08",
        "latest_shipment_date": "2026-11-30",
        "lc_expiry_date": "2026-12-31",
        "presentation_period_days": 21,
        "payment_method": "LC at sight",
        "incoterm": "CIF",
        "incoterm_named_place": "Chittagong",
        "quantity": 100,
        "quantity_unit": "MT",
        "amount": 1250000,
        "currency": "USD",
        "booking_reference": None,
    }
    return [
        _make_field(
            case_id,
            fallback_document,
            name,
            value,
            f"Fallback MVP extraction for {name}: {value}",
            confidence=0.66,
        )
        for name, value in values.items()
    ]


def _try_llm_extraction(case_id: str, document: dict, raw_text: str, diagnostic: dict | None = None) -> list[dict] | None:
    if os.getenv("LLM_EXTRACTION_TEST_INVALID_JSON") == "true":
        if diagnostic is not None:
            diagnostic["warnings"].append("LLM extraction returned malformed JSON in test mode; using fallback parser.")
        return None
    if os.getenv("DOCUMENT_EXTRACTION_MODE", "AUTO").upper() == "FALLBACK_ONLY":
        return None
    if os.getenv("USE_LLM_EXTRACTION", "").lower() != "true" or not os.getenv("OPENAI_API_KEY"):
        return None
    fields = _llm_extract_fields(document, raw_text)
    if fields is None:
        if diagnostic is not None:
            diagnostic["warnings"].append("LLM extraction failed or returned invalid JSON; using fallback parser.")
        return None
    validated, warnings = validate_extracted_fields(fields, document)
    if diagnostic is not None:
        diagnostic["llm_used"] = bool(validated)
        diagnostic["warnings"].extend(warnings)
    if not validated:
        return None
    return [
        _make_field(
            case_id,
            document,
            str(item.get("field_name")),
            item.get("value"),
            str(item.get("evidence_text") or f"LLM extracted {item.get('field_name')}: {item.get('value')}"),
            confidence=_bounded_confidence(item.get("confidence")),
        )
        for item in validated
    ]


def _llm_extract_fields(document: dict, raw_text: str) -> list[dict] | None:
    field_names = [
        "case_name",
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
        "port_of_loading",
        "port_of_discharge",
        "final_destination",
        "vessel",
        "route",
        "etd",
        "eta",
        "latest_shipment_date",
        "lc_expiry_date",
        "presentation_period_days",
        "applicant",
        "beneficiary",
        "shipper",
        "consignee",
    ]
    prompt = (
        "Extract trade document fields as strict JSON. Return only an object with a fields array. "
        "Each item must contain field_name, value, evidence_text, confidence. "
        f"Allowed field_name values: {', '.join(field_names)}. "
        "Use amount only for monetary value, and currency only for currency code. "
        "Use quantity for the numeric cargo quantity and quantity_unit for its unit. "
        "For example, 'Quantity: 5000 metric tons' must become quantity=5000 and quantity_unit='metric tons', not amount. "
        "Do not include units in amount. "
        "Do not infer legal conclusions, risk levels, conflicts, approvals, or monitoring decisions.\n\n"
        f"Document type: {document.get('document_type')}\n"
        f"Filename: {document.get('filename')}\n"
        f"Text:\n{raw_text[:12000]}"
    )
    payload = {
        "model": os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": "You extract structured trade facts with short evidence snippets."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        fields = parsed.get("fields")
        return fields if isinstance(fields, list) else None
    except (KeyError, json.JSONDecodeError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return None


def _bounded_confidence(value) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.75


def _extract_value(field_name: str, raw_text: str, document: dict):
    patterns = {
        "vessel": r"vessel[:\s]+([A-Z0-9 -]+)",
        "route": r"route[:\s]+([A-Za-z ]+\s*->\s*[A-Za-z ]+(?:\s*->\s*[A-Za-z ]+)?)",
        "port_of_loading": r"(?:port of loading|pol)[:\s]+([A-Za-z ]+)",
        "port_of_discharge": r"(?:port of discharge|pod)[:\s]+([A-Za-z ]+)",
        "final_destination": r"final destination[:\s]+([A-Za-z ]+)",
        "etd": r"\betd\)?[^0-9]{0,24}?([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2} [A-Za-z]+ [0-9]{4})",
        "eta": r"\beta\)?[^0-9]{0,24}?([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2} [A-Za-z]+ [0-9]{4})",
        "latest_shipment_date": r"latest (?:date of )?shipment[:\s]+([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2} [A-Za-z]+ [0-9]{4})",
        "lc_expiry_date": r"(?:lc expiry|expiry date)[:\s]+([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2} [A-Za-z]+ [0-9]{4})",
        "presentation_period_days": r"presentation period[:\s]+([0-9]+)",
        "payment_method": r"payment(?: method| terms)?[:\s]+([A-Za-z ]+)",
        "incoterm": r"(?:incoterm[:\s]+)?\b(CIF|CFR|CIP|CPT|FOB|FCA|FAS|EXW|DAP|DPU|DDP)\b",
        "incoterm_named_place": r"(?:incoterm[: \t]+)?(?:CIF|CFR|CIP|CPT|FOB|FCA|FAS|EXW|DAP|DPU|DDP)[ \t]+([A-Za-z][A-Za-z .'-]+)",
        "amount": r"amount[:\s]+(?:USD|US\$|\$)?\s*([0-9,]+(?:\.[0-9]+)?)",
        "currency": r"currency[:\s]+([A-Z]{3})",
        "booking_reference": r"booking reference[:\s]+([A-Z0-9-]+)",
        "lc_number": r"lc number[:\s]+([A-Z0-9-]+)",
        "issuing_bank": r"issuing bank[:\s]+([A-Za-z0-9 .,&-]+)",
        "applicant": r"applicant[:\s]+([A-Za-z0-9 .,&-]+)",
        "beneficiary": r"beneficiary[:\s]+([A-Za-z0-9 .,&-]+)",
        "commodity": r"commodity[:\s]+([A-Za-z0-9 .,&-]+)",
        "quantity": r"quantity[:\s]+([A-Za-z0-9 .,&-]+)",
        "quantity_unit": r"quantity[:\s]+[0-9,]+(?:\.[0-9]+)?\s*([A-Za-z][A-Za-z .,&-]*)",
        "buyer": r"buyer[:\s]+([A-Za-z0-9 .,&-]+)",
        "seller": r"seller[:\s]+([A-Za-z0-9 .,&-]+)",
        "shipper": r"shipper[:\s]+([A-Za-z0-9 .,&-]+)",
        "consignee": r"consignee[:\s]+([A-Za-z0-9 .,&-]+)",
    }
    match = re.search(patterns.get(field_name, r"$^"), raw_text, re.IGNORECASE)
    if match:
        value = match.group(1).strip(" .,\r\n")
        if field_name in {"amount", "presentation_period_days"}:
            return _float_or_int(value)
        if field_name == "quantity":
            return _quantity_number(value)
        return _normalize_date(value) if "date" in field_name or field_name in {"etd", "eta"} else value
    return None


def _default_value(field_name: str):
    defaults = {
        "vessel": "CAPEMOLLINI",
        "route": "Shanghai -> Chittagong -> Dhaka",
        "port_of_loading": "Shanghai",
        "port_of_discharge": "Chittagong",
        "final_destination": "Dhaka",
        "etd": "2026-11-25",
        "eta": "2026-12-08",
        "latest_shipment_date": "2026-11-30",
        "lc_expiry_date": "2026-12-31",
        "presentation_period_days": 21,
        "payment_method": "LC at sight",
        "incoterm": "CIF",
        "incoterm_named_place": "Chittagong",
        "quantity": 100,
        "quantity_unit": "MT",
        "amount": 1250000,
        "currency": "USD",
        "partial_shipment_allowed": True,
        "transshipment_allowed": True,
    }
    return defaults.get(field_name)


def _overall_extraction_status(diagnostics: list[dict]) -> str:
    statuses = {item.get("status") for item in diagnostics}
    if not diagnostics:
        return "FAILED"
    if "SUCCESS" in statuses and len(statuses) == 1:
        return "SUCCESS"
    if "SUCCESS" in statuses or "PARTIAL" in statuses:
        return "PARTIAL"
    if "NEEDS_VISION" in statuses:
        return "NEEDS_VISION"
    if "UNSUPPORTED" in statuses:
        return "UNSUPPORTED"
    return "FAILED"


def _make_field(case_id: str, document: dict, field_name: str, value, raw_text: str, confidence: float | None = None) -> dict:
    global _field_counter
    field = {
        "field_id": f"FIELD-{_field_counter:03d}",
        "case_id": case_id,
        "field_name": field_name,
        "display_name": field_name.replace("_", " ").title(),
        "value": value,
        "source_document_id": document["document_id"],
        "source_document_name": document["filename"],
        "evidence_text": _evidence_text(field_name, value, raw_text),
        "page_number": 1,
        "confidence": confidence if confidence is not None else (0.9 if value is not None else 0.45),
        "requires_confirmation": field_name in CRITICAL_FIELDS,
        "review_status": "PENDING",
        "edited_value": None,
    }
    _field_counter += 1
    return field


def _perspective_field(case_id: str, extracted: list[dict]) -> dict:
    global _field_counter
    detection = detect_trade_perspective(extracted)
    field = {
        "field_id": f"FIELD-{_field_counter:03d}",
        "case_id": case_id,
        "field_name": "trade_perspective",
        "display_name": "Trade Perspective",
        "value": detection["perspective"],
        "source_document_id": detection.get("source_document_id"),
        "source_document_name": detection.get("source_document_name"),
        "evidence_text": detection["evidence_text"],
        "page_number": 1,
        "confidence": detection["confidence"],
        "requires_confirmation": True,
        "review_status": "PENDING",
        "edited_value": None,
        "detection_source": detection["source"],
        "detection_basis": detection["basis"],
    }
    _field_counter += 1
    return field


def _evidence_text(field_name: str, value, raw_text: str) -> str:
    if value is None:
        return f"No direct evidence found for {field_name}; fallback review required."
    for line in raw_text.splitlines():
        if str(value).lower() in line.lower():
            return line.strip()[:400]
    return f"Extracted {field_name}: {value}"


def _dedupe_fields(fields: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for field in fields:
        existing = best.get(field["field_name"])
        if existing is None or field["confidence"] > existing["confidence"]:
            best[field["field_name"]] = field
    return list(best.values())


def _find_field(case_id: str, field_id: str) -> dict:
    if case_id not in _fields:
        _fields[case_id] = load_item("extracted_fields", case_id) or []
    for field in _fields.get(case_id, []):
        if field["field_id"] == field_id:
            return field
    raise KeyError(field_id)


def _float_or_int(value):
    if value in {None, ""}:
        return None
    try:
        number = float(str(value).replace(",", ""))
    except ValueError as error:
        raise ValueError(f"Invalid numeric amount: {value}") from error
    return int(number) if number.is_integer() else number


def _quantity_number(value):
    if value in {None, ""}:
        return None
    match = re.match(r"^([0-9][0-9,]*(?:\.[0-9]+)?)", str(value).strip())
    if not match:
        return value
    number = float(match.group(1).replace(",", ""))
    return int(number) if number.is_integer() else number


def _int_or_none(value):
    return None if value in {None, ""} else int(value)


def _normalize_date(value: str) -> str:
    value = value.strip()
    if re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", value):
        return value
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value


def add_days(date_value: str, days: int | None) -> str:
    if not date_value or days is None:
        return ""
    return (datetime.fromisoformat(date_value).date() + timedelta(days=days)).isoformat()


def _doc_type(case_id: str, document_id: str) -> str:
    for document in get_documents(case_id):
        if document["document_id"] == document_id:
            return document.get("document_type", "UNKNOWN")
    return "UNKNOWN"


def _persist_documents(case_id: str) -> None:
    save_item("documents", case_id, _documents.get(case_id, []), case_id)


def _persist_fields(case_id: str) -> None:
    save_item("extracted_fields", case_id, _fields.get(case_id, []), case_id)


def _persist_conflicts(case_id: str) -> None:
    save_item("field_conflicts", case_id, _field_conflicts.get(case_id, []), case_id)
