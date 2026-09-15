from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.database import Base


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(100), nullable=True)  # e.g., "Senior Hair Stylist", "Skin Care Specialist"
    working_days = Column(String(200), default="Monday,Tuesday,Wednesday,Thursday,Friday,Saturday")  # Comma-separated days
    working_start = Column(String(10), default="10:00")  # HH:MM 24-hr format
    working_end = Column(String(10), default="19:00")    # HH:MM 24-hr format
    break_start = Column(String(10), default="14:00")      # HH:MM 24-hr format
    break_end = Column(String(10), default="14:30")        # HH:MM 24-hr format
    supported_services = Column(Text, nullable=True)     # Comma-separated service names or JSON list
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business", back_populates="staff_members")
