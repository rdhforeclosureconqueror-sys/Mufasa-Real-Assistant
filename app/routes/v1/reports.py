from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import ProgressRecord, QuestParticipant, User

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/quest/{quest_id}")
def quest_report(quest_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    enrolled = db.scalar(select(func.count(QuestParticipant.id)).where(QuestParticipant.quest_id == quest_id)) or 0
    completed = db.scalar(
        select(func.count(ProgressRecord.id)).where(ProgressRecord.quest_id == quest_id, ProgressRecord.completed.is_(True))
    ) or 0
    avg_points = db.scalar(select(func.avg(ProgressRecord.total_points)).where(ProgressRecord.quest_id == quest_id)) or 0
    return {
        "quest_id": quest_id,
        "enrolled": enrolled,
        "completed": completed,
        "completion_rate": (completed / enrolled) if enrolled else 0,
        "avg_points": round(float(avg_points), 2),
    }
