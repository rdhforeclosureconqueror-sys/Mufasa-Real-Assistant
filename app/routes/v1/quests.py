from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import OrgMembership, Organization, Quest, QuestCheckpoint, QuestParticipant, RoleName, User
from app.schemas.quest import CheckpointCreate, EnrollRequest, QuestCreate

router = APIRouter(prefix="/api/v1/quests", tags=["quests"])


def _assert_org_admin(db: Session, user: User, org_id: int) -> None:
    if user.system_role == RoleName.SYSTEM_ADMIN:
        return
    membership = db.scalar(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user.id,
            OrgMembership.role.in_([RoleName.PARTNER_ADMIN]),
        )
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Org admin required")


@router.post("")
def create_quest(payload: QuestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org = db.get(Organization, payload.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    _assert_org_admin(db, user, payload.org_id)
    quest = Quest(
        org_id=payload.org_id,
        title=payload.title,
        description=payload.description,
        enforce_order=payload.enforce_order,
    )
    db.add(quest)
    db.commit()
    return {"id": quest.id, "title": quest.title}


@router.post("/checkpoints")
def create_checkpoint(payload: CheckpointCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quest = db.get(Quest, payload.quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    _assert_org_admin(db, user, quest.org_id)
    duplicate_position = db.scalar(
        select(QuestCheckpoint).where(
            QuestCheckpoint.quest_id == payload.quest_id,
            QuestCheckpoint.position == payload.position,
        )
    )
    if duplicate_position:
        raise HTTPException(status_code=409, detail="Checkpoint position already exists for quest")

    duplicate_qr = db.scalar(
        select(QuestCheckpoint).where(
            QuestCheckpoint.quest_id == payload.quest_id,
            QuestCheckpoint.qr_code == payload.qr_code,
        )
    )
    if duplicate_qr:
        raise HTTPException(status_code=409, detail="QR code already exists for quest")

    cp = QuestCheckpoint(**payload.model_dump())
    db.add(cp)
    quest.points_total += cp.points
    db.commit()
    return {"id": cp.id, "quest_id": cp.quest_id, "position": cp.position}


@router.post("/enroll")
def enroll(payload: EnrollRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quest = db.get(Quest, payload.quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    if user.system_role != RoleName.SYSTEM_ADMIN and payload.user_id != user.id:
        _assert_org_admin(db, user, quest.org_id)

    enrolling_user = db.get(User, payload.user_id)
    if not enrolling_user:
        raise HTTPException(status_code=404, detail="User not found")

    exists = db.scalar(
        select(QuestParticipant).where(QuestParticipant.quest_id == payload.quest_id, QuestParticipant.user_id == payload.user_id)
    )
    if exists:
        return {"ok": True, "message": "already enrolled"}

    db.add(QuestParticipant(quest_id=payload.quest_id, user_id=payload.user_id))
    db.commit()
    return {"ok": True}
