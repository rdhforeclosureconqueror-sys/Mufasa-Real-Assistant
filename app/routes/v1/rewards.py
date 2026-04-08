from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import ProgressRecord, Reward, RewardRedemption, User

router = APIRouter(prefix="/api/v1/rewards", tags=["rewards"])


@router.get("/{org_id}")
def list_rewards(org_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rewards = db.scalars(select(Reward).where(Reward.org_id == org_id)).all()
    return [{"id": r.id, "name": r.name, "points_cost": r.points_cost} for r in rewards]


@router.post("/{reward_id}/redeem")
def redeem(reward_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reward = db.get(Reward, reward_id)
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")

    total_points = sum(r.total_points for r in db.scalars(select(ProgressRecord).where(ProgressRecord.user_id == user.id)).all())
    spent_points = sum(db.get(Reward, rr.reward_id).points_cost for rr in db.scalars(select(RewardRedemption).where(RewardRedemption.user_id == user.id)).all())
    if total_points - spent_points < reward.points_cost:
        raise HTTPException(status_code=400, detail="Not enough points")

    redemption = RewardRedemption(reward_id=reward.id, user_id=user.id)
    db.add(redemption)
    db.commit()
    return {"ok": True, "redemption_id": redemption.id}
