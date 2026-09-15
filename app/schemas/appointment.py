from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict


class AppointmentCreate(BaseModel):
    business_id: int
    customer_id: int
    service_id: int | None = None
    staff_id: int | None = None
    event_type: str | None = None
    appointment_date: date
    appointment_time: time
    venue: str | None = None
    guests: int | None = None
    notes: str | None = None


class AppointmentResponse(BaseModel):
    id: int
    business_id: int
    customer_id: int
    service_id: int | None
    staff_id: int | None
    event_type: str | None
    appointment_date: date
    appointment_time: time
    venue: str | None
    guests: int | None
    status: str
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentUpdate(BaseModel):
    appointment_date: date | None = None
    appointment_time: time | None = None
    venue: str | None = None
    guests: int | None = None
    notes: str | None = None