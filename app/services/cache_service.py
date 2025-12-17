# file: app/services/cache_service.py

import json
from app.core.redis import cache_get, cache_set, cache_delete

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 dias


async def get_cached_session(vendor_id: int, phone: str):
    key = f"session:{vendor_id}:{phone}"
    value = await cache_get(key)
    if not value:
        return None
    try:
        return json.loads(value)
    except:
        return None


async def save_cached_session(vendor_id: int, phone: str, conversation_id: int, chatwoot_conv_id: str):
    key = f"session:{vendor_id}:{phone}"
    data = {
        "conversation_id": conversation_id,
        "chatwoot_conv_id": chatwoot_conv_id,
    }
    await cache_set(key, json.dumps(data), ttl_seconds=SESSION_TTL_SECONDS)


async def invalidate_cached_session(vendor_id: int, phone: str):
    key = f"session:{vendor_id}:{phone}"
    await cache_delete(key)


# ============================================================
# REPLY MAPPING (WAID ↔ CWID)
# ============================================================

REPLY_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 dias (recomendado)

async def save_reply_mapping_both(cw_msg_id: int, wa_msg_id: str):
    """
    Salva:
    - CW → WA  (para Chatwoot responder no WhatsApp)
    - WA → CW  (para exibir reply no Chatwoot)
    """
    key_cw = f"cw:{cw_msg_id}:waid"
    key_wa = f"wa:{wa_msg_id}:cwid"

    await cache_set(key_cw, wa_msg_id, ttl_seconds=REPLY_TTL_SECONDS)
    await cache_set(key_wa, str(cw_msg_id), ttl_seconds=REPLY_TTL_SECONDS)


async def get_waid_from_cwid(cw_msg_id: int) -> str | None:
    """
    Retorna o WA messageId de um CW message_id.
    """
    key = f"cw:{cw_msg_id}:waid"
    return await cache_get(key)


async def get_cwid_from_waid(wa_msg_id: str) -> int | None:
    """
    Retorna o CW message_id de um WA messageId.
    Esse é o mapeamento necessário para exibir reply no Chatwoot.
    """
    key = f"wa:{wa_msg_id}:cwid"
    cw_id = await cache_get(key)
    return int(cw_id) if cw_id else None


async def delete_reply_mapping(cw_msg_id: int):
    key = f"cw:{cw_msg_id}:waid"
    await cache_delete(key)
