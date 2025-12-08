# file: app/api/v1/webhooks_chatwoot.py

import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.vendors_service import get_vendor_by_agent_id
from app.services.conversations_service import ensure_conversation
from app.services.sessions_service import ensure_session
from app.services.messages_service import log_message
from app.services.zapi_service import zapi_client, ZAPIError
from app.schemas.messages_log import MessageLogCreate

from app.services.cache_service import (
    get_cached_session,
    save_cached_session,
)

from app.models.conversations import Conversation
from app.utils.file_proxy import download_and_push_to_r2
from app.utils.profiler import now, step

router = APIRouter()
logger = logging.getLogger("webhooks_chatwoot")


# ============================================================
# Utils
# ============================================================

def _detect_message_type(payload: dict) -> str:
    if payload.get("content") and not payload.get("attachments"):
        return "text"

    att = payload.get("attachments", [])
    att = att[0] if att else None
    if not att:
        return "unknown"

    ft = (att.get("file_type") or "").lower()

    if "image" in ft:
        return "image"
    if "video" in ft:
        return "video"
    if "audio" in ft:
        return "audio"
    if "pdf" in ft or "document" in ft:
        return "document"

    return "unknown"


def _extract_contact_id(payload: dict) -> str | None:
    meta = payload.get("conversation", {}).get("meta", {})
    sender = meta.get("sender", {})

    identifier = sender.get("identifier") or sender.get("phone_number")
    return identifier


def _prepare_media_url(url: str) -> str:
    if "/blobs/redirect/" in url:
        return url.replace("/blobs/redirect/", "/disk/")
    return url


async def _prepare_media_for_zapi(att: dict):
    data_url = _prepare_media_url(att.get("data_url"))
    if not data_url:
        logger.warning("⚠️ attachment sem data_url")
        return None

    T = now()
    try:
        blob_url, mime = await download_and_push_to_r2(data_url)
        step(T, "download + upload para R2")
        logger.info(f"[CW->ZAPI] mídia enviada ao R2: {blob_url}")
        return blob_url, mime

    except Exception as e:
        logger.error(f"❌ erro preparando mídia: {e}")
        return None


# ============================================================
# PROCESSAMENTO ASSÍNCRONO
# ============================================================

async def process_message_async(payload: dict, db: Session):

    if payload.get("private"):
        logger.info("🛑 Mensagem privada ignorada")
        return

    # --------------------------------------------------------
    # 1) Identificar contato (grupo ou individual)
    # --------------------------------------------------------
    contact_id = _extract_contact_id(payload)
    if not contact_id:
        logger.warning("⚠️ [CW->ZAPI] sem contact_id")
        return

    # Na Z-API, grupos = xxx-group
    is_group = contact_id.endswith("-group")

    # --------------------------------------------------------
    # 2) Vendor / Agente
    # --------------------------------------------------------
    agent_id = payload.get("sender", {}).get("id")
    if not agent_id:
        logger.warning("⚠️ [CW->ZAPI] missing agent_id")
        return

    vendor = get_vendor_by_agent_id(db, agent_id)
    if not vendor:
        logger.warning("⚠️ [CW->ZAPI] vendor not found")
        return

    # --------------------------------------------------------
    # 3) Garantir conversa interna
    # --------------------------------------------------------
    conversation = ensure_conversation(
        db,
        phone=contact_id,
        vendor_id=vendor.vendor_id
    )

    # Destino para Z-API
    if is_group:
        # grupo: mandar exatamente o id xxx-group
        target = contact_id
    else:
        # somente números
        target = "".join(filter(str.isdigit, contact_id))

    if not target:
        logger.warning("⚠️ [CW->ZAPI] target vazio")
        return

    # --------------------------------------------------------
    # 4) Cache da sessão
    # --------------------------------------------------------
    session_cached = await get_cached_session(vendor.vendor_id, contact_id)

    if session_cached:
        conversation_id = session_cached["conversation_id"]
        chatwoot_conv_id = session_cached["chatwoot_conv_id"]
        conversation = db.get(Conversation, conversation_id)
    else:
        conversation_id = conversation.conversation_id
        chatwoot_conv_id = str(payload.get("conversation", {}).get("id"))
        await save_cached_session(
            vendor.vendor_id,
            contact_id,
            conversation_id,
            chatwoot_conv_id
        )

    # --------------------------------------------------------
    # 5) Criar session
    # --------------------------------------------------------
    session = ensure_session(
        db,
        conversation_id=conversation_id,
        vendor_id=vendor.vendor_id,
        chatwoot_conv_id=chatwoot_conv_id,
        zapi_lid=""
    )

    # --------------------------------------------------------
    # 6) Conteúdo
    # --------------------------------------------------------
    msg_type = _detect_message_type(payload)
    content = payload.get("content") or ""
    att = payload.get("attachments", [])
    att = att[0] if att else None

    # 👉 REMOVIDO prefixo com nome do agente.
    # Para grupo, vai mandar exatamente o que o atendente escreveu.

    # --------------------------------------------------------
    # 7) Envio para Z-API
    # --------------------------------------------------------
    try:
        if msg_type == "text":
            result = zapi_client.send_text(
                vendor.instance_id,
                vendor.instance_token,
                target,
                content or ""
            )

        elif msg_type in ["image", "video", "audio", "document"]:
            prepared = await _prepare_media_for_zapi(att)
            if not prepared:
                logger.error("❌ [CW->ZAPI] falha preparando mídia")
                return

            blob_url, mime = prepared

            if msg_type == "image":
                result = zapi_client.send_image(
                    vendor.instance_id, vendor.instance_token,
                    target, blob_url, caption=content or ""
                )

            elif msg_type == "video":
                result = zapi_client.send_video(
                    vendor.instance_id, vendor.instance_token,
                    target, blob_url, caption=content or ""
                )

            elif msg_type == "audio":
                result = zapi_client.send_audio(
                    vendor.instance_id, vendor.instance_token,
                    target, blob_url
                )

            elif msg_type == "document":
                ext = (att.get("file_type") or "pdf").split("/")[-1]
                result = zapi_client.send_document(
                    vendor.instance_id, vendor.instance_token,
                    target, blob_url, extension=ext
                )
        else:
            logger.info(f"ℹ️ [CW->ZAPI] tipo não suportado: {msg_type}")
            return

        logger.info(f"✅ [CW->ZAPI] enviado → {result}")

    except ZAPIError as e:
        logger.error(f"❌ erro enviando para z-api: {e}")
        return

    # --------------------------------------------------------
    # 8) Log interno
    # --------------------------------------------------------
    msg_log = MessageLogCreate(
        conversation_id=conversation_id,
        session_id=session.session_id,
        vendor_id=vendor.vendor_id,
        direction="outgoing",
        source="chatwoot",
        message_type=msg_type,
        content=content,
    )
    log_message(db, msg_log)


# ============================================================
# Webhook principal
# ============================================================

@router.post("")
async def chatwoot_webhook(
    payload: dict,
    background: BackgroundTasks,
    db: Session = Depends(get_db)
):
    if payload.get("event") != "message_created":
        return {"ignored": True, "reason": "not_message_created"}

    if payload.get("message_type") != "outgoing":
        return {"ignored": True, "reason": "not_outgoing"}

    if payload.get("private"):
        return {"ignored": True, "reason": "private_message"}

    background.add_task(process_message_async, payload, db)

    return {"status": "accepted"}
