from sqlalchemy import Column, String, Boolean, DateTime, Integer
from sqlalchemy.sql import func
import uuid
from app.db.base import Base

class Vendor(Base):
    __tablename__ = "vendors"

    vendor_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Dados do vendedor
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)

    # Chatwoot
    agent_id = Column(Integer, nullable=False)
    inbox_identifier = Column(String, nullable=False)

    # Z-API
    instance_id = Column(String, nullable=False, unique=True)
    instance_token = Column(String, nullable=False)

    # Status
    active = Column(Boolean, nullable=False, default=True)

    # Auditoria
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
