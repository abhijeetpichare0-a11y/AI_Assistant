from sqlalchemy import Column, Integer, String, Boolean
from app.database.database import Base

class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False)
    time_slot = Column(String, nullable=False)
    is_booked = Column(Boolean, default=False)
