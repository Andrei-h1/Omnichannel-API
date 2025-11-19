from pydantic import BaseModel

class ConversationBase(BaseModel):
    customer_phone: str
    current_vendor_id: str | None = None
    status: str = "open"

class ConversationCreate(ConversationBase):
    pass

class ConversationUpdate(BaseModel):
    current_vendor_id: str | None = None
    status: str | None = None

class ConversationRead(ConversationBase):
    conversation_id: str

    class Config:
        orm_mode = True