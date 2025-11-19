from pydantic import BaseModel

class ConversationSessionBase(BaseModel):
    conversation_id: str
    vendor_id: str
    chatwoot_conv_id: str
    zapi_chat_lid: str

class ConversationSessionCreate(ConversationSessionBase):
    pass

class ConversationSessionUpdate(BaseModel):
    end_at: str | None = None

class ConversationSessionRead(ConversationSessionBase):
    session_id: str

    class Config:
        orm_mode = True
