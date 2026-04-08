from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=120)


class QuestCreate(BaseModel):
    org_id: int
    title: str = Field(min_length=2, max_length=160)
    description: str = ""
    enforce_order: bool = True


class CheckpointCreate(BaseModel):
    quest_id: int
    title: str = Field(min_length=2, max_length=160)
    position: int = Field(ge=1)
    qr_code: str = Field(min_length=2, max_length=180)
    points: int = Field(default=10, ge=0)


class EnrollRequest(BaseModel):
    quest_id: int
    user_id: int = Field(ge=1)


class CheckInRequest(BaseModel):
    quest_id: int
    qr_code: str = Field(min_length=2, max_length=180)
