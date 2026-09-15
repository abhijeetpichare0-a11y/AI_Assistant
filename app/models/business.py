from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False)  # e.g., Salon & Spa, Clinic, Gym, Restaurant
    owner_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=False)
    services_text = Column("services", Text, nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)
    currency = Column(String(10), default="INR")
    operating_hours = Column(String(100), default="10:00 AM - 08:00 PM")
    timezone = Column(String(50), default="Asia/Kolkata")
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    services = relationship("Service", back_populates="business", cascade="all, delete-orphan")
    staff_members = relationship("Staff", back_populates="business", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="business", cascade="all, delete-orphan")
    resources = relationship("BusinessResource", back_populates="business", cascade="all, delete-orphan")
    rules = relationship("BusinessRule", back_populates="business", cascade="all, delete-orphan")
    faqs = relationship("BusinessFAQ", back_populates="business", cascade="all, delete-orphan")
    documents = relationship("BusinessDocument", back_populates="business", cascade="all, delete-orphan")
    business_hours = relationship("BusinessHours", back_populates="business", cascade="all, delete-orphan")

