# Mufasa Real Assistant — Deep Dive Repository Report (April 8, 2026)

## 1) Executive Summary

This repository now includes both backend and frontend components that can run as a single cohesive service:

- **Backend**: FastAPI app in `main.py` provides chat, storyboard, and voice passthrough endpoints.
- **Frontend**: HTML/CSS/JS portal experience served directly by the same FastAPI server.
- **State persistence**: QA logs and storyboard JSON persist in `DATA_DIR` (`/data` by default).

Recent cohesion improvements implemented in this update:

1. Backend now serves the frontend entrypoint and static assets directly.
2. Added `/api/chat` compatibility route for existing frontend code.
3. Unified frontend request payload/response handling with backend schema.
4. Added comprehensive route smoke test script that validates all API routes.

---

## 2) Architecture Overview

### Backend (FastAPI)

- **Runtime**: Python + FastAPI
- **AI provider**: OpenAI-compatible `chat.completions` via official OpenAI SDK
- **Persistence**:
  - QA logs: `${DATA_DIR}/knowledge/qa_<ts>.json`
  - Storyboards: `${DATA_DIR}/storyboards/<id>.json`
- **Optional sidecars**:
  - STT via `STT_URL`
  - TTS via `TTS_URL`

### Frontend

- Static HTML/JS/CSS app (portal/chat experience).
- Uses browser speech synthesis and optional speech recognition.
- Calls backend chat API to get assistant responses.

### Cohesion/Deployment Model

The service can now be deployed as **one process**:

- `uvicorn main:app --host 0.0.0.0 --port 8000`
- Open `http://localhost:8000/`
- Frontend and backend are served from the same origin.

---

## 3) Capability Inventory

### A) Conversational Assistant
- Endpoint: `POST /ask`
- Input: `{ question, user_id?, session_id?, mode?, context? }`
- Output: QA record including generated `answer`
- Requires: `OPENAI_API_KEY`

### B) Frontend Compatibility Chat
- Endpoint: `POST /api/chat`
- Behavior: alias/proxy to `/ask`
- Purpose: preserve compatibility with portal UI scripts

### C) Voice Synthesis (Passthrough)
- Endpoint: `POST /voice/tts`
- Form field: `text`
- Behavior: forwards request to `TTS_URL/tts`, returns `audio/wav`

### D) Speech Recognition (Passthrough)
- Endpoint: `POST /voice/stt`
- Upload field: `file`
- Behavior: forwards request to `STT_URL/stt`, returns JSON

### E) Storyboard Generation
- Endpoint: `POST /storyboard/generate`
- Input: `{ question, user_id?, max_slides? }`
- Output: generated lesson deck JSON + persisted storyboard ID

### F) Storyboard Retrieval
- Endpoint: `GET /storyboard/get?id=<id>`
- Output: persisted storyboard JSON

### G) Health & Service Metadata
- `GET /health`
- `GET /api`

### H) Self-Hosted Frontend/Assets
- `GET /` serves `index.html`
- `GET /{asset_path}` serves static files within repository scope

---

## 4) API Route Validation Results

Run:

```bash
python scripts/test_api_routes.py
```

Coverage includes:

- `GET /`
- `GET /api`
- `GET /health`
- `POST /ask` (validation + no-key path)
- `POST /api/chat` (compatibility route)
- `POST /voice/tts` (validation + no-provider path)
- `POST /voice/stt` (validation + no-provider path)
- `POST /storyboard/generate` (no-key path)
- `GET /storyboard/get` (missing id + not-found id)
- Static asset route sanity (`GET /js/config.js`)

Interpretation of expected 503s:
- Without external secrets/services configured, these are correct and indicate explicit dependency guarding.

---

## 5) Current State and Gaps

### Strengths
- Clean, minimal backend surface.
- Deterministic persistence of outputs to JSON.
- Frontend now runs from same origin and route contracts are aligned.
- Route smoke tests provide quick regression detection.

### Remaining Gaps to reach full production cohesion
1. **Auth + tenancy**: no user auth, no per-tenant data isolation.
2. **Schema/versioning**: route contracts are implicit; no OpenAPI examples/tests for payload evolution.
3. **Observability**: no structured logging/metrics/tracing.
4. **Data lifecycle**: no retention policy or migrations for persisted JSON data.
5. **Resilience**: no retry/circuit-breaker strategy for upstream STT/TTS/LLM providers.
6. **Automated CI**: route smoke tests exist but not yet wired into CI pipeline.

---

## 6) Suggested Next Steps (Roadmap)

1. Add environment profiles (`.env.example`) and startup docs for local/full mode.
2. Add Pytest suite with integration tests and contract snapshots.
3. Add auth middleware + user/session scoping for persisted knowledge artifacts.
4. Add typed API client for frontend to centralize request/response handling.
5. Add Dockerfile + docker-compose for one-command local stack.
6. Add GitHub Actions workflow: lint + tests + smoke checks.

---

## 7) Quick Runbook

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# open http://localhost:8000
python scripts/test_api_routes.py
```

If you need full chat generation, set:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4.1-mini
```

Optional voice passthrough:

```bash
export STT_URL=https://your-stt-service
export TTS_URL=https://your-tts-service
```
