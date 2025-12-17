from pydantic import BaseModel
from typing import Optional


# ===========================================
# Sub-schemas
# ===========================================

class BotSessionKnown(BaseModel):
    cnpj: Optional[str] = None
    state: Optional[str] = None
    segment: Optional[str] = None
    vendor: Optional[str] = None  # vendor_id


class BotSessionAttempts(BaseModel):
    ask_cnpj: int = 0
    ask_state: int = 0
    ask_segment: int = 0
    ask_vendor: int = 0


# ===========================================
# Base
# ===========================================

class BotSessionBase(BaseModel):
    conversation_id: str
    completed: bool = False
    entity_type: str  # "lead" | "client"
    known: BotSessionKnown
    attempts: BotSessionAttempts


# ===========================================
# Create
# ===========================================

class BotSessionCreate(BaseModel):
    conversation_id: str
    initial_known: BotSessionKnown = BotSessionKnown()


# ===========================================
# Update (futuro)
# ===========================================

class BotSessionUpdate(BaseModel):
    completed: Optional[bool] = None
    known: Optional[BotSessionKnown] = None
    attempts: Optional[BotSessionAttempts] = None


# ===========================================
# Read
# ===========================================

class BotSessionRead(BotSessionBase):
    session_id: str

    class Config:
        orm_mode = True
