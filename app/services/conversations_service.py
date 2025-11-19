from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.conversations import Conversation
from app.schemas.conversations import ConversationCreate, ConversationUpdate

CONVERSATION_TTL_DAYS = 30


def get_last_conversation(db: Session, phone: str) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(Conversation.customer_phone == phone)
        .order_by(Conversation.last_active_at.desc().nullslast())
        .first()
    )


def create_conversation(db: Session, data: ConversationCreate) -> Conversation:
    conv = Conversation(**data.model_dump())
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def ensure_conversation(db: Session, phone: str, vendor_id: str) -> Conversation:
    """
    Regra principal do Omnichannel:
    - Se não existe conversa → cria nova
    - Se existe mas está expirada (30 dias) → cria nova
    - Se existe e é recente → reaproveita
    - Se vendedor mudou → reatribui
    - Sempre atualiza last_active_at
    """

    now = datetime.now()
    conv = get_last_conversation(db, phone)

    # ============================
    # Caso 1 — Nunca existiu
    # ============================
    if not conv:
        data = ConversationCreate(
            customer_phone=phone,
            current_vendor_id=vendor_id,
            status="open"
        )
        return create_conversation(db, data)

    # ============================
    # Caso 2 — last_active_at está NULL
    # ============================
    if not conv.last_active_at:
        conv.last_active_at = now
        conv.current_vendor_id = vendor_id
        db.commit()
        db.refresh(conv)
        return conv

    # ============================
    # Caso 3 — conversa expirada (> 30 dias)
    # ============================
    ttl_limit = now - timedelta(days=CONVERSATION_TTL_DAYS)
    if conv.last_active_at < ttl_limit:
        data = ConversationCreate(
            customer_phone=phone,
            current_vendor_id=vendor_id,
            status="open"
        )
        return create_conversation(db, data)

    # ============================
    # Caso 4 — conversa ativa
    # ============================
    if conv.current_vendor_id != vendor_id:
        conv.current_vendor_id = vendor_id

    conv.last_active_at = now
    db.commit()
    db.refresh(conv)
    return conv


def update_conversation(db: Session, conv: Conversation, data: ConversationUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(conv, field, value)
    db.commit()
    db.refresh(conv)
    return conv


def close_conversation(db: Session, conv: Conversation):
    conv.status = "closed"
    db.commit()
    db.refresh(conv)
    return conv
