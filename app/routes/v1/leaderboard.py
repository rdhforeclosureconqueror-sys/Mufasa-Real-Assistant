from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import ProgressRecord, User

router = APIRouter(prefix="/api/v1/leaderboard", tags=["leaderboard"])


@router.get("/{quest_id}")
def leaderboard(quest_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(
        select(ProgressRecord).where(ProgressRecord.quest_id == quest_id).order_by(desc(ProgressRecord.total_points))
    ).all()
    return [{"user_id": r.user_id, "points": r.total_points, "completed": r.completed} for r in rows]
