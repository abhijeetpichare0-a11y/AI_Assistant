from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class BusinessRule(Base):
    __tablename__ = "business_rules"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    rule_key = Column(String(100), nullable=False)  # e.g., "min_notice_minutes", "cancellation_notice_hours", "deposit_percentage", "late_arrival_minutes", "max_group_size"
    rule_value = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business", back_populates="rules")
