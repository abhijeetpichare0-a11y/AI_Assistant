from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class CustomerCreate(BaseModel):
    business_id: int
    name: str
    phone: str
    email: EmailStr | None = None


class CustomerResponse(BaseModel):
    id: int
    business_id: int
    name: str
    phone: str
    email: EmailStr | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)