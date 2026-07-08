# ForeSail

This MVP demonstrates a case-aware monitoring agent for one trade shipment case. It supports demo-case monitoring, agent orchestration, evidence-backed document extraction, field confirmation, obligation/deadline mapping, information gap detection, and action draft generation.

## MVP Boundary

MVP 2.0 can upload and parse TXT, DOCX, and text-based PDF files. Image OCR is not enabled. If extraction cannot parse a file, the API returns a parse error and can fall back to deterministic MVP extraction for the demo flow.

This MVP does not connect to real AIS, weather, news, port, banking, insurance, FX, TMS, ERP, or email APIs.

## Demo Case

- Vessel: CAPEMOLLINI
- Route: Shanghai -> Chittagong -> Dhaka
- Port of Loading: Shanghai
- Port of Discharge: Chittagong
- Final Destination: Dhaka
- ETD: 2026-11-25
- ETA: 2026-12-08
- Latest shipment date: 2026-11-30
- Payment method: LC at sight
- Incoterm: CIF

## Backend

From `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```text
GET http://127.0.0.1:8000/api/health
```

## Frontend

From `frontend/`:

```powershell
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Tests

From `backend/`:

```powershell
python -m unittest discover app/tests
```

The tests verify:

- The five mock events match expected classifications.
- Score thresholds match MVP requirements.
- Relevant events move the case into risk states.
- Continue Monitoring moves the case to `MONITORING`.
- Risk exposures are mapped as expected.
- Action generation deduplicates repeated exposure actions.
- Document upload and extraction return evidence-backed fields.
- Field approval/edit/reject and confirm-fields flow works.
- Agent run returns obligations, information gaps, and action drafts.

## Supported Demo Flow

1. Open the frontend.
2. Optionally select files on the create page.
3. Click `Create Demo Case`.
4. Upload Contract / PO, Booking Confirmation, and Letter of Credit documents.
5. Click `Extract Documents`.
6. Review extracted fields, evidence text, confidence, and approve/edit/reject fields.
7. Click `Confirm Fields` to generate confirmed case facts.
8. Review Case Snapshot, Case Watch Profile, and initial Status Timeline.
9. Click `Run Agent Monitoring Cycle`.
10. Review Agent Run Summary and Agent Run Trace.
11. Review Event Relevance Results.
12. Review Obligation & Deadline Map, Information Gaps, and Action Drafts.
13. Review Risk Trigger / Exposure Summary and Recommended Action Board.
14. Click `Continue Monitoring`.
15. Confirm status transitions through `DRAFT -> ACTIVE -> WATCHING -> AT_RISK -> ACTION_REQUIRED -> MONITORING`.

## Agent Orchestration

The `MonitoringAgent` layer orchestrates deterministic services in order:

1. Load case
2. Load confirmed fields
3. Retrieve watch profile
4. Fetch mock events
5. Classify events with the relevance engine
6. Map exposures
7. Map obligations and deadlines
8. Detect information gaps
9. Generate actions
10. Generate action drafts
11. Update status through the state machine
12. Generate an agent run summary and trace

Core business decisions remain deterministic. The agent layer does not perform event scoring, classification, exposure mapping, status transition, action deduplication, or date/money calculation.

## Optional LLM Summary

By default, external events are fetched in **REAL** mode from Open-Meteo, RSS search, and GDELT connectors (all enabled by default). Agent summaries are generated deterministically and do not require an API key unless you opt in.

Recommended local setup:

```powershell
cd backend
copy .env.example .env
```

Then edit `backend/.env` as needed:

```text
EVENT_SOURCE_MODE=REAL
OPEN_METEO_ENABLED=true
REAL_SEARCH_ENABLED=true
GDELT_ENABLED=true
USE_LLM_SUMMARY=false
REQUIRE_LLM_AGENT=false
OPENAI_API_KEY=your_openai_api_key
OPENAI_SUMMARY_MODEL=gpt-4.1-mini
```

Restart the backend after changing `.env`.

If `REQUIRE_LLM_AGENT=true`, the agent run **must attempt** an LLM summary. If the key is missing or the LLM call fails, monitoring results still return HTTP 200 with a deterministic fallback summary and a `summary_warning` in the trace.

If `REQUIRE_LLM_AGENT=false` or omitted, the backend can fall back to deterministic summary when no key is configured. LLM output is never used for scoring, classification, exposure mapping, status transition, or action generation.

## Optional LLM Extraction

Document extraction works without an API key by using regex/simple deterministic extraction plus MVP fallback values.

To enable LLM extraction as an optional enhancement:

```text
USE_LLM_EXTRACTION=true
OPENAI_API_KEY=your_openai_api_key
```

LLM extraction is isolated to document field extraction, evidence text support, information gap wording, and draft wording. It is not used for event scoring, classification, status transition, deadline calculation final decisions, or action deduplication.

## API Endpoints

- `POST /api/cases/demo`
- `POST /api/cases/upload`
- `GET /api/cases/{case_id}`
- `GET /api/cases/{case_id}/watch-profile`
- `POST /api/cases/{case_id}/documents/upload`
- `GET /api/cases/{case_id}/documents`
- `POST /api/cases/{case_id}/documents/extract`
- `GET /api/cases/{case_id}/extracted-fields`
- `POST /api/cases/{case_id}/extracted-fields/{field_id}/approve`
- `POST /api/cases/{case_id}/extracted-fields/{field_id}/edit`
- `POST /api/cases/{case_id}/extracted-fields/{field_id}/reject`
- `POST /api/cases/{case_id}/confirm-fields`
- `GET /api/cases/{case_id}/confirmed-facts`
- `GET /api/cases/{case_id}/obligations`
- `GET /api/cases/{case_id}/information-gaps`
- `GET /api/cases/{case_id}/action-drafts`
- `POST /api/cases/{case_id}/action-drafts/{draft_id}/regenerate`
- `GET /api/events/mock`
- `POST /api/cases/{case_id}/monitor`
- `POST /api/cases/{case_id}/agent-run`
- `GET /api/cases/{case_id}/relevance-results`
- `GET /api/cases/{case_id}/risk-summary`
- `GET /api/cases/{case_id}/actions`
- `GET /api/cases/{case_id}/status-timeline`
- `POST /api/cases/{case_id}/continue-monitoring`

## TODO After MVP 2.0

- Add persistent storage if multiple demo sessions are needed.
- Add robust PDF extraction and OCR for scanned files.
- Add authentication and role-based approval if moving beyond a local hackathon demo.
- Add real data integrations only behind explicit adapter boundaries.
