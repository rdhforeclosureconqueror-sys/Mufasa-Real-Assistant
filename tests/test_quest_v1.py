from pathlib import Path
import os
import subprocess

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.models.entities import ProgressRecord
from main import app


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str, role: str = "participant", password: str = "Passw0rd!") -> str:
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": email.split("@")[0], "role": role},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _login(client: TestClient, email: str, password: str = "Passw0rd!") -> str:
    res = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_quest_v1_end_to_end_flow(tmp_path: Path):
    db_file = tmp_path / "quest_v1.db"
    db_url = f"sqlite:///{db_file}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    migration = subprocess.run(
        ["python", "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert migration.returncode == 0, migration.stderr

    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    # 1) register users
    admin_token = _register(client, "admin@example.com", role="partner_admin")
    participant_one_token = _register(client, "participant1@example.com")
    participant_two_token = _register(client, "participant2@example.com")

    # 2) login
    participant_one_login_token = _login(client, "participant1@example.com")
    assert participant_one_login_token

    # 3) authenticated identity
    me_res = client.get("/api/v1/auth/me", headers=_auth_headers(participant_one_login_token))
    assert me_res.status_code == 200, me_res.text
    assert me_res.json()["email"] == "participant1@example.com"

    # 4) create organization
    org_res = client.post(
        "/api/v1/orgs",
        json={"name": "Quest Org", "slug": "quest-org"},
        headers=_auth_headers(admin_token),
    )
    assert org_res.status_code == 200, org_res.text
    org_id = org_res.json()["id"]

    # 5) create quest
    quest_res = client.post(
        "/api/v1/quests",
        json={"org_id": org_id, "title": "River Clean-up", "description": "Community quest", "enforce_order": True},
        headers=_auth_headers(admin_token),
    )
    assert quest_res.status_code == 200, quest_res.text
    quest_id = quest_res.json()["id"]

    # 6) create checkpoints
    cp1 = client.post(
        "/api/v1/quests/checkpoints",
        json={"quest_id": quest_id, "title": "Start", "position": 1, "qr_code": "QR-START", "points": 15},
        headers=_auth_headers(admin_token),
    )
    assert cp1.status_code == 200, cp1.text

    cp2 = client.post(
        "/api/v1/quests/checkpoints",
        json={"quest_id": quest_id, "title": "Middle", "position": 2, "qr_code": "QR-MID", "points": 25},
        headers=_auth_headers(admin_token),
    )
    assert cp2.status_code == 200, cp2.text

    cp3 = client.post(
        "/api/v1/quests/checkpoints",
        json={"quest_id": quest_id, "title": "Finish", "position": 3, "qr_code": "QR-END", "points": 35},
        headers=_auth_headers(admin_token),
    )
    assert cp3.status_code == 200, cp3.text

    duplicate_position = client.post(
        "/api/v1/quests/checkpoints",
        json={"quest_id": quest_id, "title": "Dup", "position": 3, "qr_code": "QR-OTHER", "points": 10},
        headers=_auth_headers(admin_token),
    )
    assert duplicate_position.status_code == 409

    # 7) enroll participants
    me_one = client.get("/api/v1/auth/me", headers=_auth_headers(participant_one_token)).json()["id"]
    me_two = client.get("/api/v1/auth/me", headers=_auth_headers(participant_two_token)).json()["id"]

    enroll_one = client.post(
        "/api/v1/quests/enroll",
        json={"quest_id": quest_id, "user_id": me_one},
        headers=_auth_headers(admin_token),
    )
    assert enroll_one.status_code == 200, enroll_one.text

    enroll_two = client.post(
        "/api/v1/quests/enroll",
        json={"quest_id": quest_id, "user_id": me_two},
        headers=_auth_headers(admin_token),
    )
    assert enroll_two.status_code == 200, enroll_two.text

    # 8) valid ordered QR check-ins (participant one)
    in_order_1 = client.post(
        "/api/v1/checkins",
        json={"quest_id": quest_id, "qr_code": "QR-START"},
        headers=_auth_headers(participant_one_token),
    )
    assert in_order_1.status_code == 200, in_order_1.text

    in_order_2 = client.post(
        "/api/v1/checkins",
        json={"quest_id": quest_id, "qr_code": "QR-MID"},
        headers=_auth_headers(participant_one_token),
    )
    assert in_order_2.status_code == 200, in_order_2.text

    # 8b) out-of-order rejection (participant two tries checkpoint 2 first)
    out_of_order = client.post(
        "/api/v1/checkins",
        json={"quest_id": quest_id, "qr_code": "QR-MID"},
        headers=_auth_headers(participant_two_token),
    )
    assert out_of_order.status_code == 409

    # 8c) invalid and duplicate submission handling
    invalid_qr = client.post(
        "/api/v1/checkins",
        json={"quest_id": quest_id, "qr_code": "NOT-A-REAL-QR"},
        headers=_auth_headers(participant_one_token),
    )
    assert invalid_qr.status_code == 400

    duplicate_checkin = client.post(
        "/api/v1/checkins",
        json={"quest_id": quest_id, "qr_code": "QR-MID"},
        headers=_auth_headers(participant_one_token),
    )
    assert duplicate_checkin.status_code == 200
    assert duplicate_checkin.json()["message"] == "already checked in"

    # Participant two completes first two checkpoints for leaderboard ordering.
    p2_cp1 = client.post(
        "/api/v1/checkins",
        json={"quest_id": quest_id, "qr_code": "QR-START"},
        headers=_auth_headers(participant_two_token),
    )
    assert p2_cp1.status_code == 200

    p2_cp2 = client.post(
        "/api/v1/checkins",
        json={"quest_id": quest_id, "qr_code": "QR-MID"},
        headers=_auth_headers(participant_two_token),
    )
    assert p2_cp2.status_code == 200

    # 9) complete quest (participant one finishes last checkpoint)
    complete_res = client.post(
        "/api/v1/checkins",
        json={"quest_id": quest_id, "qr_code": "QR-END"},
        headers=_auth_headers(participant_one_token),
    )
    assert complete_res.status_code == 200, complete_res.text

    progress_res = client.get(f"/api/v1/progress/{quest_id}", headers=_auth_headers(participant_one_token))
    assert progress_res.status_code == 200
    assert progress_res.json()["completed"] is True
    assert progress_res.json()["completed_count"] == 3
    assert progress_res.json()["total_points"] == 75

    # 10) retrieve leaderboard
    leaderboard_res = client.get(f"/api/v1/leaderboard/{quest_id}", headers=_auth_headers(admin_token))
    assert leaderboard_res.status_code == 200, leaderboard_res.text
    leaderboard = leaderboard_res.json()
    assert len(leaderboard) == 2
    assert leaderboard[0]["points"] == 75
    assert leaderboard[0]["completed"] is True
    assert leaderboard[1]["points"] == 40
    assert leaderboard[1]["completed"] is False

    # 11) retrieve reporting metrics
    report_res = client.get(f"/api/v1/reports/quest/{quest_id}", headers=_auth_headers(admin_token))
    assert report_res.status_code == 200, report_res.text
    report = report_res.json()
    assert report["enrolled"] == 2
    assert report["completed"] == 1
    assert report["completion_rate"] == 0.5
    assert report["avg_points"] == 57.5

    # Extra integrity verification directly at DB layer.
    with Session(engine) as db:
        records = db.scalars(select(ProgressRecord).where(ProgressRecord.quest_id == quest_id)).all()
        assert len(records) == 2

    app.dependency_overrides.clear()
