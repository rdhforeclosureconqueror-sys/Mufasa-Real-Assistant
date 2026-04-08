from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import CheckInEvent, ProgressRecord, Quest, QuestCheckpoint, QuestParticipant, User
from app.schemas.quest import CheckInRequest

router = APIRouter(prefix="/api/v1/checkins", tags=["checkins"])


@router.post("")
def qr_checkin(payload: CheckInRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quest = db.get(Quest, payload.quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    enrollment = db.scalar(
        select(QuestParticipant).where(QuestParticipant.quest_id == payload.quest_id, QuestParticipant.user_id == user.id)
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="User is not enrolled")

    checkpoint = db.scalar(
        select(QuestCheckpoint).where(QuestCheckpoint.quest_id == payload.quest_id, QuestCheckpoint.qr_code == payload.qr_code)
    )
    if not checkpoint:
        raise HTTPException(status_code=400, detail="Invalid QR code")

    already = db.scalar(
        select(CheckInEvent).where(CheckInEvent.user_id == user.id, CheckInEvent.quest_id == payload.quest_id, CheckInEvent.checkpoint_id == checkpoint.id)
    )
    if already:
        return {"ok": True, "message": "already checked in"}

    if quest.enforce_order:
        completed_positions = db.scalars(
            select(QuestCheckpoint.position)
            .join(CheckInEvent, CheckInEvent.checkpoint_id == QuestCheckpoint.id)
            .where(CheckInEvent.user_id == user.id, CheckInEvent.quest_id == payload.quest_id)
        ).all()
        expected = (max(completed_positions) + 1) if completed_positions else 1
        if checkpoint.position != expected:
            raise HTTPException(status_code=409, detail=f"Checkpoint order enforced. Expected position {expected}")

    db.add(CheckInEvent(quest_id=quest.id, checkpoint_id=checkpoint.id, user_id=user.id, raw_payload={"qr_code": payload.qr_code}))

    progress = db.scalar(select(ProgressRecord).where(ProgressRecord.quest_id == quest.id, ProgressRecord.user_id == user.id))
    if not progress:
        progress = ProgressRecord(quest_id=quest.id, user_id=user.id)
        db.add(progress)

    progress.completed_count += 1
    progress.total_points += checkpoint.points
    total_checkpoints = len(db.scalars(select(QuestCheckpoint.id).where(QuestCheckpoint.quest_id == quest.id)).all())
    progress.completed = progress.completed_count >= total_checkpoints
    progress.updated_at = datetime.utcnow()

    db.commit()
    return {"ok": True, "completed_count": progress.completed_count, "total_points": progress.total_points}
