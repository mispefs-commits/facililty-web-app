from pydantic import BaseModel, EmailStr, Field, field_validator
from .security import check_password_strength


class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = ""
    password: str

    @field_validator("password")
    @classmethod
    def strong(cls, v):
        check_password_strength(v)
        return v


class UserCreate(RegisterIn):
    role: str
    site_ids: list[int] = []


class UserPatch(BaseModel):
    is_active: bool | None = None
    site_ids: list[int] | None = None
    role: str | None = None


class SiteIn(BaseModel):
    region: str = Field(min_length=2)
    name: str = Field(min_length=2)
    code: str = Field(min_length=2, max_length=30)
    address: str = ""


class BuildingIn(BaseModel):
    site_id: int
    name: str = Field(min_length=1)


class TowerIn(BaseModel):
    building_id: int
    name: str = Field(min_length=1)


class FloorIn(BaseModel):
    building_id: int
    tower_id: int | None = None
    name: str = Field(min_length=1)


class CategoryIn(BaseModel):
    name: str = Field(min_length=2)
    default_priority: str = "Medium"
    team: str = ""


class TicketIn(BaseModel):
    site_id: int
    building_id: int
    tower_id: int | None = None
    floor_id: int | None = None
    location: str = Field(min_length=2, max_length=200)
    asset_id: str = ""
    category_id: int
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=5000)
    priority: str | None = None
    source: str = "Web Portal"
    client_name: str = Field(default="", max_length=150)
    rep_name: str = Field(default="", max_length=120)
    rep_phone: str = ""
    rep_whatsapp: str = ""


class AssignIn(BaseModel):
    assignee_id: int
    note: str = ""


class StatusIn(BaseModel):
    status: str
    note: str = ""
    root_cause: str = ""
    corrective_action: str = ""
    closure_remarks: str = ""


class PriorityIn(BaseModel):
    priority: str
    note: str = ""


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=3000)
    internal: bool = False


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class ReopenIn(BaseModel):
    reason: str = Field(min_length=3)
