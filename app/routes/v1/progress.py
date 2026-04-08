from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import ProgressRecord, User

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


@router.get("/{quest_id}")
def get_progress(quest_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    progress = db.scalar(select(ProgressRecord).where(ProgressRecord.quest_id == quest_id, ProgressRecord.user_id == user.id))
    if not progress:
        return {"quest_id": quest_id, "completed_count": 0, "total_points": 0, "completed": False}
    return {
        "quest_id": quest_id,
        "completed_count": progress.completed_count,
        "total_points": progress.total_points,
        "completed": progress.completed,
    }
