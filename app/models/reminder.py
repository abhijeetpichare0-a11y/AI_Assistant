from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id"),
        nullable=False
    )

    business_id = Column(
        Integer,
        ForeignKey("businesses.id"),
        nullable=False
    )

    reminder_type = Column(
        String(50),
        nullable=False
    )

    scheduled_at = Column(
        DateTime,
        nullable=False
    )

    sent_at = Column(
        DateTime,
        nullable=True
    )

    status = Column(
        String(50),
        default="pending",
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    appointment = relationship(
        "Appointment",
        back_populates="reminders"
    )