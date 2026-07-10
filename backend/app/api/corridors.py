from fastapi import APIRouter

from app.services.corridor_risk_service import list_corridor_states

router = APIRouter(prefix="/api/corridors", tags=["corridors"])


@router.get("")
def list_corridors() -> dict:
    return {"corridors": list_corridor_states()}
