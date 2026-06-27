import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


_load_env_file()

from app.api.cases import router as cases_router
from app.api.documents import router as documents_router
from app.api.events import router as events_router
from app.api.monitoring import router as monitoring_router
from app.api.treatment_plans import router as treatment_plans_router

app = FastAPI(title="ForeSail")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases_router)
app.include_router(documents_router)
app.include_router(events_router)
app.include_router(monitoring_router)
app.include_router(treatment_plans_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "mvp-3.0"}
