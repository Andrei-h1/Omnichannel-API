from datetime import datetime
from sqlalchemy.orm import Session

from app.models.conversation_sessions import ConversationSession
from app.schemas.conversation_sessions import ConversationSessionCreate


def get_active_session(db: Session, conversation_id: str) -> ConversationSession | None:
    return (
        db.query(ConversationSession)
        .filter(
            ConversationSession.conversation_id == conversation_id,
            ConversationSession.end_at.is_(None)
        )
        .first()
    )


def close_session(db: Session, session: ConversationSession):
    session.end_at = datetime.utcnow()  # CORRETO: UTC
    db.commit()
    db.refresh(session)
    return session


def create_session(db: Session, data: ConversationSessionCreate):
    session = ConversationSession(**data.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def ensure_session(db: Session, conversation_id: str, vendor_id: str, zapi_lid: str, chatwoot_conv_id: str):
    active = get_active_session(db, conversation_id)

    # se não tem sessão ativa → cria nova
    if not active:
        return create_session(
            db,
            ConversationSessionCreate(
                conversation_id=conversation_id,
                vendor_id=vendor_id,
                zapi_chat_lid=zapi_lid,
                chatwoot_conv_id=chatwoot_conv_id
            )
        )

    # se mudou de vendedor → fecha anterior e cria nova
    if active.vendor_id != vendor_id:
        close_session(db, active)
        return create_session(
            db,
            ConversationSessionCreate(
                conversation_id=conversation_id,
                vendor_id=vendor_id,
                zapi_chat_lid=zapi_lid,
                chatwoot_conv_id=chatwoot_conv_id
            )
        )

    # mesmo vendedor → apenas atualiza ids externos
    active.zapi_chat_lid = zapi_lid
    active.chatwoot_conv_id = chatwoot_conv_id
    db.commit()
    db.refresh(active)
    return active
