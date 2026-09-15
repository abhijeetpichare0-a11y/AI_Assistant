from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    business_id = Column(
        Integer,
        ForeignKey("businesses.id"),
        nullable=False
    )

    service_id = Column(
        Integer,
        ForeignKey("services.id"),
        nullable=True
    )

    staff_id = Column(
        Integer,
        ForeignKey("staff.id"),
        nullable=True
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False
    )

    event_type = Column(
        String(100),
        nullable=False
    )

    appointment_date = Column(
        Date,
        nullable=False
    )

    appointment_time = Column(
        Time,
        nullable=False
    )

    venue = Column(
        String(200),
        nullable=True
    )

    guests = Column(
        Integer,
        nullable=True
    )

    status = Column(
        String(50),
        default="confirmed",
        nullable=False
    )

    notes = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    customer = relationship(
        "Customer",
        back_populates="appointments"
    )

    reminders = relationship(
        "Reminder",
        back_populates="appointment",
        cascade="all, delete-orphan"
    )

    business = relationship(
        "Business",
        back_populates="appointments"
    )

    service = relationship("Service")
    staff = relationship("Staff")