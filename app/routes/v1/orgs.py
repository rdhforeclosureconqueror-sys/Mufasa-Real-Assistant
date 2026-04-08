from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import OrgMembership, Organization, RoleName, User
from app.schemas.quest import OrganizationCreate

router = APIRouter(prefix="/api/v1/orgs", tags=["orgs"])


@router.post("")
def create_org(payload: OrganizationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.system_role not in {RoleName.PARTNER_ADMIN, RoleName.SYSTEM_ADMIN}:
        raise HTTPException(status_code=403, detail="Only admins can create orgs")
    existing = db.scalar(select(Organization).where((Organization.slug == payload.slug) | (Organization.name == payload.name)))
    if existing:
        raise HTTPException(status_code=409, detail="Organization name or slug already exists")
    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    db.flush()
    db.add(OrgMembership(org_id=org.id, user_id=user.id, role=RoleName.PARTNER_ADMIN))
    db.commit()
    return {"id": org.id, "name": org.name, "slug": org.slug}


@router.get("/{org_id}/members")
def list_members(org_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = db.scalar(select(OrgMembership).where(OrgMembership.org_id == org_id, OrgMembership.user_id == user.id))
    if not membership and user.system_role != RoleName.SYSTEM_ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized for this org")
    members = db.scalars(select(OrgMembership).where(OrgMembership.org_id == org_id)).all()
    return [{"user_id": m.user_id, "role": m.role} for m in members]
