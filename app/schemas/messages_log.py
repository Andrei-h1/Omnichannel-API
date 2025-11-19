from pydantic import BaseModel

class MessageLogBase(BaseModel):
    conversation_id: str
    session_id: str | None = None
    vendor_id: str | None = None
    direction: str
    source: str
    message_type: str
    content: str | None = None

class MessageLogCreate(MessageLogBase):
    pass

class MessageLogRead(MessageLogBase):
    log_id: str

    class Config:
        orm_mode = True
