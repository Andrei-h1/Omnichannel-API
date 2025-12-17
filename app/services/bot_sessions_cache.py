import json
import uuid
from typing import Optional

from app.core.redis import cache_get, cache_set, cache_delete
from app.schemas.bot_sessions import (
    BotSessionRead,
    BotSessionKnown,
    BotSessionAttempts,
)

# ============================================================
# Config
# ============================================================

BOT_SESSION_TTL = 60 * 60 * 2  # 2 horas


def _redis_key(conversation_id: str) -> str:
    return f"bot_session:active:{conversation_id}"


# ============================================================
# Public API
# ============================================================

async def get_active_bot_session(
    conversation_id: str,
) -> Optional[BotSessionRead]:
    """
    Retorna a sessão ativa ou None.
    """
    key = _redis_key(conversation_id)
    raw = await cache_get(key)

    # Nada no Redis
    if not raw:
        return None

    try:
        data = json.loads(raw)

        # 🔒 validação mínima de contrato
        if not isinstance(data, dict):
            await cache_delete(key)
            return None

        if not data.get("session_id"):
            await cache_delete(key)
            return None

        return BotSessionRead(**data)

    except Exception:
        # se der erro de parse ou validação, remove a chave
        await cache_delete(key)
        return None


async def save_bot_session(session: BotSessionRead):
    """
    Persiste sessão ativa no Redis com TTL.
    """
    key = _redis_key(session.conversation_id)

    payload = session.dict()
    await cache_set(
        key=key,
        value=json.dumps(payload),
        ttl_seconds=BOT_SESSION_TTL,
    )


async def delete_bot_session(conversation_id: str):
    """
    Remove sessão ativa (ex: quando completed).
    """
    key = _redis_key(conversation_id)
    await cache_delete(key)


# ============================================================
# Factory (Create)
# ============================================================

def build_bot_session(
    *,
    conversation_id: str,
    entity_type: str,
    known: BotSessionKnown,
) -> BotSessionRead:
    """
    Cria uma nova sessão em memória (não salva).
    """
    return BotSessionRead(
        session_id=f"sess_{uuid.uuid4().hex}",
        conversation_id=conversation_id,
        completed=False,
        entity_type=entity_type,
        known=known,
        attempts=BotSessionAttempts(),
    )
