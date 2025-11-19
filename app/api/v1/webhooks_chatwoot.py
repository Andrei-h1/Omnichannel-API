import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.settings import settings
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
# UTILS
# ============================================================
def _normalize_phone(p: str | None) -> str | None:
    if not p:
        return None
    p = "".join(filter(str.isdigit, str(p)))
    if not p:
        return None
    if not p.startswith("+"):
        p = "+" + p
    return p


def _extract_phone(payload: dict) -> str | None:
    convo = payload.get("conversation", {})
    meta = convo.get("meta", {})
    sender = meta.get("sender", {})

    print(">> PHONE DEBUG:", sender)

    phone = sender.get("phone_number") or sender.get("identifier")
    return _normalize_phone(phone)


def _extract_agent_id(payload: dict) -> int | None:
    return (
        payload.get("sender", {}).get("id")
        or payload.get("sender_id")
        or payload.get("user", {}).get("id")
    )


def _extract_content(payload: dict) -> str | None:
    return payload.get("content")


def _extract_attachment(payload: dict) -> dict | None:
    atts = payload.get("attachments", [])
    return atts[0] if atts else None


def _detect_message_type(payload: dict) -> str:
    if payload.get("content") and not payload.get("attachments"):
        return "text"

    att = _extract_attachment(payload)
    if not att:
        return "unknown"

    ft = att.get("file_type", "").lower()

    if "image" in ft:
        return "image"
    if "video" in ft:
        return "video"
    if "audio" in ft:
        return "audio"
    if "pdf" in ft or "document" in ft:
        return "document"
    return "unknown"


def _phone_to_zapi(phone: str | None) -> str | None:
    if not phone:
        return None
    return "".join(filter(str.isdigit, phone))


# ============================================================
# MEDIA HANDLER (R2)
# ============================================================
async def _prepare_media_for_zapi(att: dict) -> tuple[str, str] | None:
    print("⚪ Entrou no _prepare_media_for_zapi")

    data_url = att.get("data_url")
    if not data_url:
        logger.warning("⚠️ [CW->ZAPI] attachment sem data_url")
        return None

    T1 = now()

    try:
        blob_url, mime = await download_and_push_to_r2(data_url)
        step(T1, "Download + Upload para Cloudflare R2")

        logger.info(f"📦 [MEDIA] R2 OK → {blob_url}")
        return blob_url, mime

    except Exception as e:
        logger.error(f"❌ [MEDIA] erro no preparo da mídia (R2): {e}")
        return None


# ============================================================
# PROCESSAMENTO ASSÍNCRONO
# ============================================================
async def process_message_async(payload: dict, db: Session):

    if payload.get("private") is True:
        logger.info("🛑 [CW -> ZAPI] Mensagem privada ignorada")
        return

    # 1) Telefone
    phone = _extract_phone(payload)
    if not phone:
        logger.warning("⚠️ [CW->ZAPI] missing_phone")
        return

    phone_zapi = _phone_to_zapi(phone)
    if not phone_zapi:
        return

    # 2) Vendor
    agent_id = _extract_agent_id(payload)
    if not agent_id:
        return

    vendor = get_vendor_by_agent_id(db, agent_id)
    if not vendor:
        return

    # ============================================================
    # 3) REDIS: tentar recuperar sessão existente
    # ============================================================
    session_cached = await get_cached_session(vendor.vendor_id, phone)

    if session_cached:
        conversation_id = session_cached["conversation_id"]
        chatwoot_conv_id = session_cached["chatwoot_conv_id"]

        conversation = db.get(Conversation, conversation_id)

        logger.info(
            f"♻️ [CACHE] Sessão carregada: conv_id={conversation_id} cw_id={chatwoot_conv_id}"
        )

    else:
        conversation = ensure_conversation(
            db,
            phone=phone,
            vendor_id=vendor.vendor_id,
        )
        conversation_id = conversation.conversation_id
        chatwoot_conv_id = str(payload.get("conversation", {}).get("id"))

        await save_cached_session(
            vendor.vendor_id,
            phone,
            conversation_id,
            chatwoot_conv_id
        )

        logger.info(
            f"💾 [CACHE] Sessão salva: conv_id={conversation_id} cw_id={chatwoot_conv_id}"
        )

    # 4) Session
    session = ensure_session(
        db,
        conversation_id=conversation_id,
        vendor_id=vendor.vendor_id,
        chatwoot_conv_id=chatwoot_conv_id,
        zapi_lid=""
    )

    # 5) Tipos / Conteúdo / Anexo
    msg_type = _detect_message_type(payload)
    content = _extract_content(payload)
    att = _extract_attachment(payload)

    logger.info(
        f"➡️ [CW->ZAPI BG] type={msg_type} phone={phone} vendor={vendor.vendor_id}"
    )

    # 6) Envio para ZAPI
    try:
        if msg_type == "text":

            T2 = now()
            result = zapi_client.send_text(
                vendor.instance_id,
                vendor.instance_token,
                phone_zapi,
                content or "",
            )
            step(T2, "Z-API respondeu (texto)")

        elif msg_type in ["image", "video", "audio", "document"]:

            prepared = await _prepare_media_for_zapi(att)

            if not prepared:
                logger.error("❌ [CW->ZAPI] Erro no preparo da mídia. Abortando.")
                return

            blob_url, _mime = prepared

            T3 = now()

            if msg_type == "image":
                result = zapi_client.send_image(
                    vendor.instance_id,
                    vendor.instance_token,
                    phone_zapi,
                    blob_url,
                    caption=content or "",
                )

            elif msg_type == "video":
                result = zapi_client.send_video(
                    vendor.instance_id,
                    vendor.instance_token,
                    phone_zapi,
                    blob_url,
                    caption=content or "",
                )

            elif msg_type == "audio":
                result = zapi_client.send_audio(
                    vendor.instance_id,
                    vendor.instance_token,
                    phone_zapi,
                    blob_url,
                )

            elif msg_type == "document":
                ft = att.get("file_type", "") or ""
                ext = ft.split("/")[-1] if "/" in ft else "pdf"
                result = zapi_client.send_document(
                    vendor.instance_id,
                    vendor.instance_token,
                    phone_zapi,
                    blob_url,
                    extension=ext,
                )

            step(T3, "Z-API respondeu ao envio da mídia")

        else:
            logger.info(f"ℹ️ [CW->ZAPI] Tipo não suportado: {msg_type}")
            return

    except ZAPIError as e:
        logger.error(f"❌ [CW->ZAPI] Erro enviando para ZAPI: {e}")
        return

    logger.info(f"✅ [CW->ZAPI] Enviado com sucesso → {result}")

    # 7) Log no BD
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
# WEBHOOK PRINCIPAL
# ============================================================
@router.post("")
async def chatwoot_webhook(
    payload: dict,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    T0 = now()

    print("=== DEBUG CHATWOOT WEBHOOK IN ===")
    print(payload)
    print("=== END ===")

    step(T0, "Webhook recebido do Chatwoot")

    if payload.get("event") != "message_created":
        return {"ignored": True, "reason": "not_message_created"}

    if payload.get("message_type") != "outgoing":
        return {"ignored": True, "reason": "not_outgoing"}

    if payload.get("private") is True:
        return {"ignored": True, "reason": "private_message_blocked"}

    background.add_task(process_message_async, payload, db)

    return {"status": "accepted"}
