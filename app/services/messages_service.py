from sqlalchemy.orm import Session
from app.models.messages_log import MessageLog
from app.schemas.messages_log import MessageLogCreate


def log_message(db: Session, data: MessageLogCreate) -> MessageLog:
    msg = MessageLog(**data.model_dump())
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
