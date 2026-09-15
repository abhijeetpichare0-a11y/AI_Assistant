from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BusinessBase(BaseModel):
    name: str
    category: str
    owner_name: Optional[str] = None
    phone: str
    services_text: str
    location: Optional[str] = None
    operating_hours: Optional[str] = "10:00 AM - 08:00 PM"
    timezone: Optional[str] = "UTC"
    status: Optional[str] = "active"

class BusinessCreate(BusinessBase):
    pass

class BusinessResponse(BusinessBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
