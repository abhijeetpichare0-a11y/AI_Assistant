from pydantic import BaseModel
from typing import Optional, List


class BusinessOnboardRequest(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    phone: str
    email: Optional[str] = None
    location: Optional[str] = None
    currency: Optional[str] = "INR"
    timezone: Optional[str] = "Asia/Kolkata"
    supported_languages: Optional[str] = "English, Hindi"
    operating_hours: Optional[str] = "10:00 AM - 08:00 PM"


class BusinessUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    supported_languages: Optional[str] = None
    operating_hours: Optional[str] = None


class ServiceCreateRequest(BaseModel):
    name: str
    category: Optional[str] = None
    duration_minutes: Optional[int] = 30
    price: Optional[float] = 0.0
    deposit_percentage: Optional[int] = 0
    required_resource_type: Optional[str] = None
    eligibility: Optional[str] = None
    description: Optional[str] = None


class StaffCreateRequest(BaseModel):
    name: str
    role: Optional[str] = None
    working_days: Optional[str] = "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday"
    working_start: Optional[str] = "10:00"
    working_end: Optional[str] = "19:00"
    break_start: Optional[str] = "14:00"
    break_end: Optional[str] = "14:30"
    supported_services: Optional[str] = None


class DayHoursItem(BaseModel):
    day: str
    opening_time: str = "10:00"
    closing_time: str = "20:00"
    is_open: bool = True


class MultiDayHoursUpdateRequest(BaseModel):
    hours: List[DayHoursItem]


class WorkingHoursUpdateRequest(BaseModel):
    operating_hours: str
    working_days: Optional[str] = "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday"
    holidays: Optional[str] = None


class BookingRulesUpdateRequest(BaseModel):
    min_notice_hours: Optional[int] = 2
    max_advance_days: Optional[int] = 30
    cancellation_rules: Optional[str] = "Free cancellation up to 2 hours before appointment"
    rescheduling_rules: Optional[str] = "Reschedule up to 2 hours before appointment"
    booking_buffer_mins: Optional[int] = 15
    max_group_size: Optional[int] = 10
    deposit_requirements: Optional[str] = "None"
    late_arrival_rules: Optional[str] = "15-minute grace period"


class OwnerChatRequest(BaseModel):
    message: str


class OwnerChatResponse(BaseModel):
    reply: str
    action_taken: Optional[str] = None
    data: Optional[dict] = None
