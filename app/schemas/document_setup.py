from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ExtractedServiceItem(BaseModel):
    name: str
    category: Optional[str] = "General"
    price: float = 0.0
    duration_minutes: int = 30
    description: Optional[str] = ""


class ExtractedDayHours(BaseModel):
    day: str  # Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
    opening_time: str = "10:00"
    closing_time: str = "20:00"
    is_open: bool = True


class ExtractedBookingRules(BaseModel):
    min_notice_hours: int = 2
    max_advance_days: int = 30
    cancellation_rules: str = "Free cancellation up to 2 hours before appointment"
    rescheduling_rules: str = "Reschedule up to 2 hours before appointment"
    booking_buffer_mins: int = 15
    max_group_size: int = 10
    deposit_requirements: str = "None"
    late_arrival_rules: str = "15-minute grace period"


class ExtractedFAQItem(BaseModel):
    question: str
    answer: str


class ConflictItem(BaseModel):
    field: str
    item_name: Optional[str] = None
    value1: str
    source1: str
    value2: str
    source2: str
    resolution_suggestion: Optional[str] = None


class DocumentExtractionResponse(BaseModel):
    business_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    currency: str = "INR"
    services: List[ExtractedServiceItem] = Field(default_factory=list)
    business_hours: List[ExtractedDayHours] = Field(default_factory=list)
    booking_rules: ExtractedBookingRules = Field(default_factory=ExtractedBookingRules)
    faqs: List[ExtractedFAQItem] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    conflicts: List[ConflictItem] = Field(default_factory=list)
    document_ids: List[int] = Field(default_factory=list)
    document_filenames: List[str] = Field(default_factory=list)


class BusinessSetupConfirmRequest(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    phone: str
    email: Optional[str] = None
    location: Optional[str] = None
    currency: Optional[str] = "INR"
    timezone: Optional[str] = "Asia/Kolkata"
    services: List[ExtractedServiceItem] = Field(default_factory=list)
    business_hours: List[ExtractedDayHours] = Field(default_factory=list)
    booking_rules: Optional[ExtractedBookingRules] = None
    faqs: Optional[List[ExtractedFAQItem]] = Field(default_factory=list)
    document_ids: Optional[List[int]] = Field(default_factory=list)
