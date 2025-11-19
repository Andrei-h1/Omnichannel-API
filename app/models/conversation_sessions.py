from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
import uuid
from app.db.base import Base

class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    session_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    conversation_id = Column(String, ForeignKey("conversations.conversation_id"), nullable=False)
    vendor_id = Column(String, ForeignKey("vendors.vendor_id"), nullable=False)

    chatwoot_conv_id = Column(String, nullable=False)
    zapi_chat_lid = Column(String, nullable=False)

    start_at = Column(DateTime, server_default=func.now())
    end_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
