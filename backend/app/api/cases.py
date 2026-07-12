from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.case_service import (
    continue_monitoring,
    create_buyer_demo_case,
    create_case,
    create_demo_case,
    create_hormuz_demo_case,
    delete_case,
    get_actions,
    get_case,
    get_relevance_results,
    get_risk_summary,
    get_timeline,
    get_watch_profile,
    replace_case_facts,
    update_case_details,
)
from app.services.case_library_service import list_case_summaries
from app.services.demo_seed_service import seed_board
from app.services.document_service import confirm_fields, seed_demo_documents
from app.services.incoterm_rule_service import resolve_cif_responsibility
from app.services.perspective_service import (
    UNSUPPORTED_PERSPECTIVE_ERROR,
    UnsupportedPerspectiveError,
    perspective_analysis,
    update_case_perspective,
)
from app.services.hazard_service import list_hazards
from app.services.route_map_service import build_route_map

router = APIRouter(prefix="/api/cases", tags=["cases"])


class UploadPayload(BaseModel):
    file_names: list[str] = []


class CreateCasePayload(BaseModel):
    case_name: str | None = None
    buyer: str | None = None
    seller: str | None = None
    commodity: str | None = None
    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    final_destination: str | None = None
    owner: str | None = None
    notes: str | None = None


class UpdateCaseDetailsPayload(CreateCasePayload):
    pass


class TradeFactsPayload(BaseModel):
    facts: dict


class PerspectivePayload(BaseModel):
    trade_perspective: str


@router.get("")
def list_cases() -> dict:
    return {"cases": list_case_summaries()}


@router.post("/seed")
def seed_monitoring_board(force: bool = False) -> dict:
    return seed_board(force=force)


@router.post("")
def create_new_case(payload: CreateCasePayload) -> dict:
    return create_case(payload.model_dump(exclude_none=True))


@router.post("/demo")
def create_demo() -> dict:
    case = create_demo_case()
    confirm_fields(case["case_id"])
    return get_case(case["case_id"])


@router.post("/demo/imminent")
def create_imminent_demo() -> dict:
    case = create_demo_case(imminent=True)
    confirm_fields(case["case_id"])
    return get_case(case["case_id"])


@router.post("/demo/clean")
def create_clean_demo() -> dict:
    case = create_demo_case()
    seed_demo_documents(case["case_id"], conflict=False)
    return case


@router.post("/demo/conflict")
def create_conflict_demo() -> dict:
    case = create_demo_case()
    seed_demo_documents(case["case_id"], conflict=True)
    return case


@router.post("/demo/buyer")
def create_buyer_demo() -> dict:
    case = create_buyer_demo_case()
    seed_demo_documents(case["case_id"], buyer=True)
    return case


@router.post("/demo/hormuz")
def create_hormuz_demo() -> dict:
    case = create_hormuz_demo_case()
    seed_demo_documents(case["case_id"], hormuz=True)
    return case


@router.post("/upload")
def upload_case(payload: UploadPayload) -> dict:
    return create_demo_case(uploaded_files=payload.file_names)


@router.get("/{case_id}")
def read_case(case_id: str) -> dict:
    return _or_404(lambda: get_case(case_id), case_id)


@router.delete("/{case_id}")
def remove_case(case_id: str) -> dict:
    return _or_404(lambda: delete_case(case_id), case_id)


@router.post("/{case_id}/details")
def update_case_detail_fields(case_id: str, payload: UpdateCaseDetailsPayload) -> dict:
    return _or_404(lambda: update_case_details(case_id, payload.model_dump(exclude_none=True)), case_id)


@router.post("/{case_id}/trade-facts")
def apply_case_trade_facts(case_id: str, payload: TradeFactsPayload) -> dict:
    def _apply() -> dict:
        replace_case_facts(case_id, payload.facts)
        return get_case(case_id)

    return _or_404(_apply, case_id)


@router.get("/{case_id}/watch-profile")
def read_watch_profile(case_id: str) -> dict:
    return _or_404(lambda: get_watch_profile(case_id), case_id)


@router.get("/{case_id}/relevance-results")
def read_relevance_results(case_id: str) -> list[dict]:
    return _or_404(lambda: get_relevance_results(case_id), case_id)


@router.get("/{case_id}/risk-summary")
def read_risk_summary(case_id: str) -> dict:
    return _or_404(lambda: get_risk_summary(case_id), case_id)


@router.get("/{case_id}/cif-responsibility")
def read_cif_responsibility(case_id: str) -> dict:
    return _or_404(lambda: resolve_cif_responsibility(get_case(case_id)), case_id)


@router.get("/{case_id}/perspective-analysis")
def read_perspective_analysis(case_id: str, perspective: str | None = None):
    try:
        return _or_404(lambda: perspective_analysis(case_id, perspective), case_id)
    except UnsupportedPerspectiveError:
        return JSONResponse(status_code=400, content=UNSUPPORTED_PERSPECTIVE_ERROR)


@router.put("/{case_id}/perspective")
def update_perspective(case_id: str, payload: PerspectivePayload):
    try:
        return _or_404(lambda: update_case_perspective(case_id, payload.trade_perspective), case_id)
    except UnsupportedPerspectiveError:
        return JSONResponse(status_code=400, content=UNSUPPORTED_PERSPECTIVE_ERROR)


@router.get("/{case_id}/actions")
def read_actions(case_id: str) -> list[dict]:
    return _or_404(lambda: get_actions(case_id), case_id)


@router.get("/{case_id}/route-map")
def read_route_map(case_id: str) -> dict:
    return _or_404(lambda: build_route_map(case_id), case_id)


@router.get("/{case_id}/hazards")
def read_hazards(case_id: str) -> list[dict]:
    def _hazards() -> list[dict]:
        get_case(case_id)
        return list_hazards(case_id)

    return _or_404(_hazards, case_id)


@router.get("/{case_id}/status-timeline")
def read_status_timeline(case_id: str) -> list[dict]:
    return _or_404(lambda: get_timeline(case_id), case_id)


@router.post("/{case_id}/continue-monitoring")
def continue_case_monitoring(case_id: str) -> dict:
    try:
        return _or_404(lambda: continue_monitoring(case_id), case_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _or_404(factory, case_id: str):
    try:
        return factory()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}") from None
