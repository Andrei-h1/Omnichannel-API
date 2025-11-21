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
logger.setLevel(logging.INFO)


# ----------------------------------------------------------
# Utils
# ----------------------------------------------------------
def _normalize_phone(p: str | None) -> str | None:
    if not p:
        return None
    p = "".join(filter(str.isdigit, str(p)))
    if not p.startswith("+"):
        p = "+" + p
    return p


def _extract_phone(payload: dict) -> str | None:
    phone = payload.get("participantPhone") if payload.get("isGroup") else payload.get("phone")
    return _normalize_phone(phone)


def _detect_message_type(payload: dict) -> str:
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


# ----------------------------------------------------------
# WEBHOOK PRINCIPAL
# ----------------------------------------------------------
@router.post("")
async def zapi_webhook(payload: dict, db: Session = Depends(get_db)):

    logger.info("=== DEBUG ZAPI WEBHOOK IN ===")
    logger.info(payload)
    logger.info("=== END ===")

    if payload.get("type") not in ("ReceivedCallback", "SentCallback", None):
        return {"ignored": True}

    instance_id = payload.get("instanceId")
    if not instance_id:
        return {"ignored": True, "reason": "missing_instance_id"}

    vendor = get_vendor_by_instance(db, instance_id)
    if not vendor:
        return {"ignored": True, "reason": "vendor_not_found"}

    phone = _extract_phone(payload)
    if not phone:
        return {"ignored": True, "reason": "missing_phone"}

    conversation = ensure_conversation(
        db,
        phone=phone,
        vendor_id=vendor.vendor_id,
    )

    zapi_lid = payload.get("chatLid") or payload.get("participantLid") or ""
    session = ensure_session(
        db,
        conversation_id=conversation.conversation_id,
        vendor_id=vendor.vendor_id,
        zapi_lid=zapi_lid,
        chatwoot_conv_id="",  
    )

    msg_type = _detect_message_type(payload)
    content = payload.get("text", {}).get("message")

    if msg_type == "unknown":
        return {"ignored": True}

    # =====================================================
    #      MÍDIA → download → upload no R2 → enviar
    # =====================================================
    try:
        inbox_identifier = vendor.inbox_identifier

        if msg_type == "text":
            result = await chatwoot_client.send_from_zapi_payload(
                payload,
                inbox_identifier
            )

        else:
            # 1) pega url original
            media_url = _extract_media_url(payload, msg_type)
            if not media_url:
                return {"ignored": True, "reason": "missing_media_url"}

            logger.info(f"[ZAPI] Baixando mídia original: {media_url}")

            # 2) download → upload no R2
            r2_url, mime = await download_and_push_to_r2(media_url)

            logger.info(f"[ZAPI] Mídia enviada ao R2: {r2_url}")

            # 3) monta novo payload para o Chatwoot
            patched = payload.copy()

            if msg_type == "image":
                patched["image"] = {
                    "imageUrl": r2_url,
                    "caption": payload.get("image", {}).get("caption", "")
                }
            elif msg_type == "video":
                patched["video"] = {
                    "videoUrl": r2_url,
                    "caption": payload.get("video", {}).get("caption", "")
                }
            elif msg_type == "audio":
                patched["audio"] = {"audioUrl": r2_url}
            elif msg_type == "document":
                patched["document"] = {
                    "documentUrl": r2_url,
                    "mimeType": mime
                }

            # 4) envia ao Chatwoot
            result = await chatwoot_client.send_from_zapi_payload(
                patched,
                inbox_identifier
            )

        logger.info(f"[ZAPI->CW] Resultado: {result}")

    except ChatwootError as e:
        raise HTTPException(status_code=500, detail="failed_to_forward_to_chatwoot")

    # LOG
    msg_log = MessageLogCreate(
        conversation_id=conversation.conversation_id,
        session_id=session.session_id,
        vendor_id=vendor.vendor_id,
        direction="incoming",
        source="zapi",
        message_type=msg_type,
        content=content,
    )
    log_message(db, msg_log)

    return {
        "status": "ok",
        "vendor_id": vendor.vendor_id,
        "conversation_id": conversation.conversation_id,
        "session_id": session.session_id,
        "forward_result": result,
    }
