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

from app.utils.file_proxy import download_and_cache_file
from app.core.settings import settings

router = APIRouter()
logger = logging.getLogger("webhooks_zapi")
logger.setLevel(logging.INFO)


# ----------------------------------------------------------
# Utils — normalized extractors
# ----------------------------------------------------------
def _normalize_phone(p: str | None) -> str | None:
    if not p:
        return None
    p = ''.join(filter(str.isdigit, str(p)))
    if not p.startswith("+"):
        p = "+" + p
    return p


def _extract_phone(payload: dict) -> str | None:
    """Extrai telefone do evento da ZAPI com fallback para grupos."""
    phone = payload.get("participantPhone") if payload.get("isGroup") else payload.get("phone")
    return _normalize_phone(phone)


def _extract_name(payload: dict) -> str:
    return payload.get("senderName") or payload.get("chatName") or "Cliente"


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

    # 0) Ignorar callbacks que não são mensagens
    if payload.get("type") not in ("ReceivedCallback", "SentCallback", None):
        reason = f"non_message_event_{payload.get('type')}"
        logger.info(f"[ZAPI] Ignorando evento: {reason}")
        return {"ignored": True, "reason": reason}

    # 1) instance_id da Z-API
    instance_id = payload.get("instanceId")
    if not instance_id:
        logger.warning("[ZAPI] Payload sem instanceId, ignorando")
        return {"ignored": True, "reason": "missing_instance_id"}

    # 2) buscar vendor pela instância
    vendor = get_vendor_by_instance(db, instance_id)
    if not vendor:
        reason = f"vendor_not_found_for_{instance_id}"
        logger.warning(f"[ZAPI] {reason}")
        return {"ignored": True, "reason": reason}

    logger.info(f"[ZAPI] Vendor resolvido: vendor_id={vendor.vendor_id}, "
                f"name={vendor.name}, inbox_identifier={vendor.inbox_identifier}")

    # 3) extrair telefone
    phone = _extract_phone(payload)
    if not phone:
        logger.warning("[ZAPI] Payload sem telefone, ignorando")
        return {"ignored": True, "reason": "missing_phone"}

    logger.info(f"[ZAPI] Telefone normalizado: {phone}")

    # 4) registrar conversa interna
    conversation = ensure_conversation(
        db,
        phone=phone,
        vendor_id=vendor.vendor_id,
    )
    logger.info(f"[ZAPI] Conversation interna: {conversation.conversation_id}")

    # 5) sessão interna
    zapi_lid = payload.get("chatLid") or payload.get("participantLid") or ""
    session = ensure_session(
        db,
        conversation_id=conversation.conversation_id,
        vendor_id=vendor.vendor_id,
        zapi_lid=zapi_lid,
        chatwoot_conv_id="",  # TBD na resposta do Chatwoot
    )
    logger.info(f"[ZAPI] Session interna: {session.session_id} (zapi_lid={zapi_lid})")

    # 6) tipo de mensagem
    msg_type = _detect_message_type(payload)
    content = payload.get("text", {}).get("message")

    logger.info(f"[ZAPI] Tipo de mensagem detectado: {msg_type}")

    if msg_type == "unknown":
        logger.info("[ZAPI] Mensagem vazia/ACK, ignorando")
        return {"ignored": True, "reason": "empty_or_ack"}

    # =====================================================
    # 7) Encaminhar para Chatwoot com inbox DO VENDOR
    # =====================================================
    try:
        inbox_identifier = vendor.inbox_identifier

        logger.info(
            f"[ZAPI->CW] Encaminhando para Chatwoot | "
            f"inbox_identifier={inbox_identifier}, phone={phone}, msg_type={msg_type}"
        )

        if msg_type == "text":
            result = await chatwoot_client.send_from_zapi_payload(
                payload,
                inbox_identifier
            )

        else:
            media_url = _extract_media_url(payload, msg_type)
            if not media_url:
                reason = "missing_media_url"
                logger.warning(f"[ZAPI] {reason}")
                return {"ignored": True, "reason": reason}

            logger.info(f"[ZAPI] Media original URL: {media_url}")

            file_id, mime = await download_and_cache_file(media_url)
            local_url = f"{settings.PUBLIC_BASE_URL}/v1/files/{file_id}"

            logger.info(f"[ZAPI] Media proxied URL: {local_url}")

            payload_with_local_url = payload.copy()

            if msg_type == "image":
                payload_with_local_url["image"] = {
                    "imageUrl": local_url,
                    "caption": payload.get("image", {}).get("caption", "")
                }
            elif msg_type == "video":
                payload_with_local_url["video"] = {
                    "videoUrl": local_url,
                    "caption": payload.get("video", {}).get("caption", "")
                }
            elif msg_type == "audio":
                payload_with_local_url["audio"] = {"audioUrl": local_url}
            elif msg_type == "document":
                payload_with_local_url["document"] = {
                    "documentUrl": local_url,
                    "mimeType": mime
                }

            result = await chatwoot_client.send_from_zapi_payload(
                payload_with_local_url,
                inbox_identifier
            )

        logger.info(f"[ZAPI->CW] Resultado envio Chatwoot: {result}")

    except ChatwootError as e:
        logger.error(f"❌ Erro ao enviar para Chatwoot: {e}")
        raise HTTPException(status_code=500, detail="failed_to_forward_to_chatwoot")

    # 8) log interno
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
    logger.info("[ZAPI] Message log registrado com sucesso")

    return {
        "status": "ok",
        "vendor_id": vendor.vendor_id,
        "conversation_id": conversation.conversation_id,
        "session_id": session.session_id,
        "forward_result": result,
    }
