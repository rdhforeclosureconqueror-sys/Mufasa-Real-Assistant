from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str
    slug: str


class QuestCreate(BaseModel):
    org_id: int
    title: str
    description: str = ""
    enforce_order: bool = True


class CheckpointCreate(BaseModel):
    quest_id: int
    title: str
    position: int
    qr_code: str
    points: int = 10


class EnrollRequest(BaseModel):
    quest_id: int
    user_id: int


class CheckInRequest(BaseModel):
    quest_id: int
    qr_code: str
