from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StaffBase(BaseModel):
    name: str
    role: Optional[str] = None
    is_active: bool = True
    business_id: int

class StaffCreate(StaffBase):
    pass

class StaffResponse(StaffBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
