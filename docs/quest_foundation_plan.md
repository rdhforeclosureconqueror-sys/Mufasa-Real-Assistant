# Community Quest Engine — Implementation Plan (V1)

## 1) Proposed folder structure
- `app/core`: settings, security, dependency guards.
- `app/db`: SQLAlchemy base/session.
- `app/models`: domain models for quest engine.
- `app/routes/v1`: primary product API routes.
- `app/routes/legacy`: isolated assistant/chat/voice/storyboard module.
- `alembic`: migration framework + revision history.
- `tests`: API and workflow tests.

## 2) Proposed DB models
- `User`, `ParticipantProfile`
- `Organization`, `OrgMembership`
- `Quest`, `QuestCheckpoint`, `QuestParticipant`
- `CheckInEvent`, `ProgressRecord`
- `Reward`, `RewardRedemption`
- `LeaderboardSnapshot`
- `AuditEvent`

## 3) Proposed auth strategy
- Email/password auth with hashed passwords (`passlib[bcrypt]`).
- JWT bearer tokens.
- Role model: `participant`, `partner_admin`, `system_admin`.
- Organization membership checks for scoped access.

## 4) Proposed migration plan
1. Introduce Alembic configuration.
2. Generate baseline migration with all V1 tables.
3. Require `alembic upgrade head` in setup docs.
4. Add later migrations per feature increment.

## 5) Proposed route map
- `/api/v1/auth/*`
- `/api/v1/orgs/*`
- `/api/v1/quests/*`
- `/api/v1/checkins/*`
- `/api/v1/progress/*`
- `/api/v1/leaderboard/*`
- `/api/v1/rewards/*`
- `/api/v1/reports/*`

## 6) Assistant-feature isolation strategy
- Move existing assistant functionality under `/legacy/*`.
- Keep legacy endpoints operable but outside V1 quest architecture.
- Prevent quest-critical state from being persisted in JSON legacy paths.

## 7) Exact V1 included scope
- Auth register/login/me.
- Organization creation + membership listing.
- Quest creation + checkpoint creation.
- Participant enrollment.
- Server-side QR check-in validation.
- Ordered checkpoint enforcement.
- Progress tracking and completion state.
- Leaderboard query + basic quest report metrics.

## 8) Exact V1 excluded scope
- NFC check-ins.
- AR/map gameplay systems.
- Complex reward catalogs/economy.
- Full frontend redesign.
- Multi-region analytics and enterprise audit tooling.
