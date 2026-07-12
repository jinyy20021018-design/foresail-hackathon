from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.action_set_service import (
    ActionSetError,
    clone_action_set,
    confirm_action_set,
    generate_action_set,
    get_action_set,
    list_action_sets,
    update_action_set,
)

router = APIRouter(prefix="/api/cases", tags=["action-sets"])


class ActionUpdate(BaseModel):
    action_id: str
    title: str | None = None
    owner_role: str | None = None
    priority: str | None = None
    deadline: str | None = None
    deadline_date: str | None = None
    selected: bool | None = None


class ActionSetUpdate(BaseModel):
    actions: list[ActionUpdate]


@router.post("/{case_id}/action-sets/generate")
def generate_case_action_set(case_id: str) -> dict:
    return _handle(lambda: generate_action_set(case_id), case_id)


@router.get("/{case_id}/action-sets")
def read_case_action_sets(case_id: str) -> list[dict]:
    return _handle(lambda: list_action_sets(case_id), case_id)


@router.get("/{case_id}/action-sets/{action_set_id}")
def read_case_action_set(case_id: str, action_set_id: str) -> dict:
    return _handle(lambda: get_action_set(case_id, action_set_id), case_id)


@router.put("/{case_id}/action-sets/{action_set_id}")
def update_case_action_set(case_id: str, action_set_id: str, payload: ActionSetUpdate) -> dict:
    return _handle(lambda: update_action_set(case_id, action_set_id, [item.model_dump(exclude_none=True) for item in payload.actions]), case_id)


@router.post("/{case_id}/action-sets/{action_set_id}/confirm")
def confirm_case_action_set(case_id: str, action_set_id: str) -> dict:
    return _handle(lambda: confirm_action_set(case_id, action_set_id), case_id)


@router.post("/{case_id}/action-sets/{action_set_id}/clone")
def clone_case_action_set(case_id: str, action_set_id: str) -> dict:
    return _handle(lambda: clone_action_set(case_id, action_set_id), case_id)


def _handle(factory, case_id: str):
    try:
        return factory()
    except ActionSetError as error:
        status = 503 if error.code == "LLM_GENERATION_FAILED" else 409
        return JSONResponse(status_code=status, content={"error": error.code, "message": error.message})
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Action set resource not found for case: {case_id}") from None
