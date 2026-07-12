from fastapi import APIRouter

from app.services.perspective_detection_service import load_our_company

router = APIRouter(prefix="/api/company-profile", tags=["company"])


@router.get("")
def read_company_profile() -> dict:
    profile = load_our_company()
    return {
        "name": profile.get("name") or "",
        "aliases": profile.get("aliases") or [],
        "role_note": "Seat (buyer/seller) is auto-detected per case by matching LC, contract, and B/L parties against this profile.",
    }
