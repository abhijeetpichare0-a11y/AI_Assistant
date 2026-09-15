from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReminderResponse(BaseModel):
    id: int
    business_id: int
    appointment_id: int
    reminder_type: str
    scheduled_at: datetime
    sent_at: datetime | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)