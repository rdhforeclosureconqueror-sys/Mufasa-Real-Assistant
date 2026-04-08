from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401
from app.db.session import engine
from app.routes.legacy.assistant import router as legacy_router
from app.routes.v1 import auth, checkins, leaderboard, orgs, progress, quests, reports, rewards

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.app_name, version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(orgs.router)
app.include_router(quests.router)
app.include_router(checkins.router)
app.include_router(progress.router)
app.include_router(leaderboard.router)
app.include_router(rewards.router)
app.include_router(reports.router)
app.include_router(legacy_router)


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": settings.app_name,
        "env": settings.env,
        "legacy_base": "/legacy",
        "api_base": "/api/v1",
    }


@app.get("/{asset_path:path}")
def serve_static(asset_path: str):
    normalized = asset_path.strip("/")
    target = (BASE_DIR / normalized).resolve()
    if BASE_DIR not in target.parents and target != BASE_DIR:
        return {"detail": "Invalid asset path"}
    if not target.exists() or not target.is_file():
        return {"detail": "Asset not found"}
    return FileResponse(target)
