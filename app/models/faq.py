from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class BusinessFAQ(Base):
    __tablename__ = "business_faqs"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)  # e.g., "policy", "pricing", "general", "walk-in"
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business", back_populates="faqs")
