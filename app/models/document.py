from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database.database import Base


class BusinessDocument(Base):
    __tablename__ = "business_documents"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt, csv, xlsx, etc.
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    extracted_text = Column(Text, nullable=True)
    processing_status = Column(String(50), default="uploaded")  # uploaded, processing, processed, failed
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    business = relationship("Business", back_populates="documents")
    owner = relationship("User")
