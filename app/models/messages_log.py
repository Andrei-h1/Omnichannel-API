from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
import uuid
from app.db.base import Base

class MessageLog(Base):
    __tablename__ = "messages_log"

    log_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    conversation_id = Column(String, ForeignKey("conversations.conversation_id"), nullable=False)
    session_id = Column(String, ForeignKey("conversation_sessions.session_id"), nullable=True)
    vendor_id = Column(String, ForeignKey("vendors.vendor_id"), nullable=True)

    direction = Column(String, nullable=False)  # incoming/outgoing
    source = Column(String, nullable=False)      # zapi/chatwoot
    message_type = Column(String, nullable=False)
    content = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
