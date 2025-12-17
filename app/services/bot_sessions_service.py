import logging

from app.schemas.bot_sessions import (
    BotSessionCreate,
    BotSessionRead,
)
from app.services.customers_service import get_customer_by_cnpj
from app.services.bot_sessions_cache import (
    get_active_bot_session,
    save_bot_session,
    build_bot_session,
)

logger = logging.getLogger("bot_session_service")


async def create_bot_session(payload: BotSessionCreate) -> BotSessionRead:
    """
    Cria uma bot_session se não existir uma ativa.
    Se já existir, retorna a sessão ativa.
    """

    # 1️⃣ Verifica se já existe sessão ativa
    existing = await get_active_bot_session(payload.conversation_id)
    if existing:
        logger.info(
            f"[BotSession] Sessão ativa já existe: session_id={existing.session_id}"
        )
        return existing

    # 2️⃣ Resolve entity_type
    entity_type = "lead"
    cnpj = payload.initial_known.cnpj

    if cnpj:
        customer = get_customer_by_cnpj(cnpj)
        if customer.get("found"):
            entity_type = "client"

    # 3️⃣ Cria sessão em memória
    session = build_bot_session(
        conversation_id=payload.conversation_id,
        entity_type=entity_type,
        known=payload.initial_known,
    )

    # 4️⃣ Persiste no Redis
    await save_bot_session(session)

    logger.info(
        f"[BotSession] Sessão criada: session_id={session.session_id} entity_type={entity_type}"
    )

    return session
