# Community Quest Engine (Foundation V1)

This repository is now the **official base** for a unified full-stack Community Quest Engine for nonprofit and city wellness pilots.

## Product architecture
- Primary domain APIs are under `/api/v1/*`.
- Legacy assistant/chat/voice/storyboard features are isolated under `/legacy/*`.
- Quest-critical data is stored in a relational database (Postgres recommended), not JSON files.

## Local setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy env template:
   ```bash
   cp .env.example .env
   ```
3. Set `DATABASE_URL` in `.env` (Postgres recommended).
4. Run migrations:
   ```bash
   alembic upgrade head
   ```
5. Start server:
   ```bash
   uvicorn main:app --reload
   ```

## Environment variables
- `ENV` (development/test/production)
- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ALGORITHM`
- `JWT_EXP_MINUTES`
- `OPENAI_API_KEY` (legacy assistant)
- `OPENAI_MODEL` (legacy assistant)
- `STT_URL` (legacy voice passthrough)
- `TTS_URL` (legacy voice passthrough)

## Core endpoints
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/orgs`
- `GET /api/v1/orgs/{org_id}/members`
- `POST /api/v1/quests`
- `POST /api/v1/quests/checkpoints`
- `POST /api/v1/quests/enroll`
- `POST /api/v1/checkins`
- `GET /api/v1/progress/{quest_id}`
- `GET /api/v1/leaderboard/{quest_id}`
- `GET /api/v1/rewards/{org_id}`
- `POST /api/v1/rewards/{reward_id}/redeem`
- `GET /api/v1/reports/quest/{quest_id}`

## Legacy routes (isolated)
- `POST /legacy/ask`
- `POST /legacy/api/chat`
- `POST /legacy/voice/tts`
- `POST /legacy/voice/stt`
- `POST /legacy/storyboard/generate`
- `GET /legacy/storyboard/get`

## Tests
```bash
pytest -q
```
