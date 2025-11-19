from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
import uuid
from app.db.base import Base

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_phone = Column(String, nullable=False)

    current_vendor_id = Column(String, ForeignKey("vendors.vendor_id"))

    status = Column(String, nullable=False, default="open")  # open/inactive/closed

    last_active_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
