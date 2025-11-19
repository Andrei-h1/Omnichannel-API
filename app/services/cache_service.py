# file: app/services/cache_service.py

import json
from app.core.redis import cache_get, cache_set, cache_delete

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 dias


async def get_cached_session(vendor_id: int, phone: str):
    """
    Retorna sessão cacheada, ou None.
    """
    key = f"session:{vendor_id}:{phone}"

    value = await cache_get(key)
    if not value:
        return None

    try:
        return json.loads(value)
    except:
        return None


async def save_cached_session(vendor_id: int, phone: str, conversation_id: int, chatwoot_conv_id: str):
    """
    Salva/Atualiza uma sessão no Redis.
    """
    key = f"session:{vendor_id}:{phone}"

    data = {
        "conversation_id": conversation_id,
        "chatwoot_conv_id": chatwoot_conv_id,
    }

    await cache_set(key, json.dumps(data), ttl_seconds=SESSION_TTL_SECONDS)


async def invalidate_cached_session(vendor_id: int, phone: str):
    """
    Apaga do Redis (se necessário).
    """
    key = f"session:{vendor_id}:{phone}"
    await cache_delete(key)
