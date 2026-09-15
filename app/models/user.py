from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default="user")  # "user" or "owner"
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business")
