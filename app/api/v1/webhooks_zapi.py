# file: app/api/v1/webhooks_zapi.py

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.vendors_service import get_vendor_by_instance
from app.services.conversations_service import ensure_conversation
from app.services.sessions_service import ensure_session
from app.services.messages_service import log_message
from app.services.chatwoot_service import chatwoot_client, ChatwootError
from app.schemas.messages_log import MessageLogCreate

from app.utils.file_proxy import download_and_push_to_r2

router = APIRouter()
logger = logging.getLogger("webhooks_zapi")


# ============================================================
# Utils
# ============================================================

def _extract_contact_identifier(payload: dict) -> tuple[str, str]:
    """
    Retorna:
    - contact_identifier (grupo ou pessoa)
    - contact_name
    """

    if payload.get("isGroup"):
        # GRUPO
        contact_identifier = payload.get("phone")                 # ex: "12036....-group"
        contact_name = payload.get("chatName") or "Grupo WhatsApp"
    else:
        # INDIVIDUAL
        raw_phone = payload.get("phone")
        digits = "".join(filter(str.isdigit, raw_phone or ""))

        contact_identifier = f"+{digits}"
        contact_name = payload.get("senderName") or contact_identifier

    return contact_identifier, contact_name


def _detect_msg_type(payload: dict) -> str:
    if payload.get("text", {}).get("message"):
        return "text"
    if payload.get("image"):
        return "image"
    if payload.get("video"):
        return "video"
    if payload.get("audio"):
        return "audio"
    if payload.get("document"):
        return "document"
    return "unknown"


def _extract_media_url(payload: dict, msg_type: str) -> str | None:
    obj = payload.get(msg_type)
    if not obj:
        return None

    return obj.get({
        "image": "imageUrl",
        "video": "videoUrl",
        "audio": "audioUrl",
        "document": "documentUrl",
    }.get(msg_type, ""))


# ============================================================
# WEBHOOK PRINCIPAL
# ============================================================

@router.post("")
async def zapi_webhook(payload: dict, db: Session = Depends(get_db)):

    print("\n\n========== ZAPI WEBHOOK RECEBIDO ==========")
    print(payload)
    print("===========================================\n\n")

    if payload.get("type") not in ("ReceivedCallback", "SentCallback", None):
        return {"ignored": True}

    instance_id = payload.get("instanceId")
    if not instance_id:
        return {"ignored": True, "reason": "missing_instance_id"}

    vendor = get_vendor_by_instance(db, instance_id)
    if not vendor:
        return {"ignored": True, "reason": "vendor_not_found"}

    # =====================================================
    # IDENTIFICADOR DO GRUPO OU INDIVIDUAL
    # =====================================================
    contact_identifier, contact_name = _extract_contact_identifier(payload)

    if not contact_identifier:
        return {"ignored": True, "reason": "missing_contact_identifier"}

    # Criar conversa interna
    conversation = ensure_conversation(
        db,
        phone=contact_identifier,
        vendor_id=vendor.vendor_id,
    )

    # Session
    session = ensure_session(
        db,
        conversation_id=conversation.conversation_id,
        vendor_id=vendor.vendor_id,
        zapi_lid=payload.get("participantLid") or "",
        chatwoot_conv_id="",
    )

    msg_type = _detect_msg_type(payload)
    message_text = payload.get("text", {}).get("message")

    # =====================================================
    # ENVIAR PARA CHATWOOT
    # =====================================================
    try:
        inbox_identifier = vendor.inbox_identifier

        # → TEXT
        if msg_type == "text":
            result = await chatwoot_client.send_from_zapi_payload(
                payload,
                inbox_identifier
            )

        # → MEDIA
        else:
            media_url = _extract_media_url(payload, msg_type)
            if not media_url:
                return {"ignored": True, "reason": "missing_media_url"}

            # --- CORREÇÃO AQUI: Capturar a legenda original da mídia ---
            original_media_data = payload.get(msg_type, {})
            original_caption = original_media_data.get("caption") or ""
            # -----------------------------------------------------------

            r2_url, mime = await download_and_push_to_r2(media_url)

            patched = payload.copy()
            
            if msg_type == "image":
                patched["image"] = {
                    "imageUrl": r2_url,
                    "caption": original_caption  # <--- Usando a variável correta
                }
            elif msg_type == "video":
                patched["video"] = {
                    "videoUrl": r2_url,
                    "caption": original_caption  # <--- Serve para vídeo também
                }
            elif msg_type == "audio":
                patched["audio"] = {"audioUrl": r2_url} # Áudio geralmente não tem caption, ok
            elif msg_type == "document":
                patched["document"] = {
                    "documentUrl": r2_url,
                    "mimeType": mime,
                    "caption": original_caption # Documento as vezes tem caption
                }

            result = await chatwoot_client.send_from_zapi_payload(
                patched,
                inbox_identifier
            )

    except ChatwootError:
        raise HTTPException(status_code=500, detail="failed_to_forward_to_chatwoot")

    # =====================================================
    # LOG INTERNO
    # =====================================================
    msg_log = MessageLogCreate(
        conversation_id=conversation.conversation_id,
        session_id=session.session_id,
        vendor_id=vendor.vendor_id,
        direction="incoming",
        source="zapi",
        message_type=msg_type,
        content=payload.get("text", {}).get("message") or "",
    )
    log_message(db, msg_log)

    return {
        "status": "ok",
        "conversation_id": conversation.conversation_id,
        "result": result,
    }
