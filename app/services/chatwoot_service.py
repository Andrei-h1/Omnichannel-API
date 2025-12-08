# file: app/services/chatwoot_service.py

import logging
import re
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import aiohttp

from app.core.settings import settings
from app.core.redis import cache_get, cache_set  # Redis persistente

logger = logging.getLogger("chatwoot_service")
logger.setLevel(logging.DEBUG)


class ChatwootError(Exception):
    pass


# ------------------------------------------------------------
# Detectar tipo da mensagem da Z-API
# ------------------------------------------------------------
def detect_zapi_message_type(payload: Dict[str, Any]) -> str:
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


# ============================================================
# CLIENTE DO CHATWOOT
# ============================================================
class ChatwootClient:
    def __init__(self) -> None:
        self.base_url = settings.CHATWOOT_BASE_URL.rstrip("/")
        self.api_key = settings.CHATWOOT_API_KEY
        self.timeout = aiohttp.ClientTimeout(total=15)

        logger.info(f"[CW] Inicializando ChatwootClient base_url={self.base_url}")

        if not self.base_url:
            logger.error("❌ CHATWOOT_BASE_URL não definido.")
        if not self.api_key:
            logger.error("❌ CHATWOOT_API_KEY não definido.")

    # --------------------------------------------------------
    # HEADERS
    # --------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {"api_access_token": self.api_key}

    # --------------------------------------------------------
    # Normalizar telefone individual
    # --------------------------------------------------------
    @staticmethod
    def _normalize_phone(phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        digits = re.sub(r"\D", "", str(phone))
        return digits if digits.startswith("+") else f"+{digits}"

    # --------------------------------------------------------
    # Download de mídia
    # --------------------------------------------------------
    async def _download_file(self, url: str) -> Optional[tuple[str, BytesIO, str]]:
        logger.info(f"[CW] Download mídia: {url}")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ Falha ao baixar mídia status={resp.status}")
                        return None

                    content = await resp.read()
                    content_type = resp.headers.get("Content-Type", "application/octet-stream")
                    filename = url.split("/")[-1] or "arquivo"

                    return filename, BytesIO(content), content_type

        except Exception as e:
            logger.error(f"❌ Erro no download: {e}")
            return None

    # --------------------------------------------------------
    # Criar contato
    # --------------------------------------------------------
    async def create_contact(self, inbox_identifier: str, identifier: str, name: str) -> Optional[str]:

        is_group = identifier.endswith("-group")

        # Monta payload corretamente
        if is_group:
            payload = {
                "identifier": identifier,
                "name": name
                # NÃO enviar phone_number
            }
        else:
            payload = {
                "identifier": identifier,
                "name": name,
                "phone_number": self._normalize_phone(identifier) # E.164 normal para contatos
            }

        url = f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/contacts"

        logger.info(
            f"[CW] create_contact inbox={inbox_identifier} "
            f"id={identifier} is_group={is_group}"
        )

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=self._headers()) as resp:
                    text = await resp.text()

                    if resp.status != 200:
                        logger.error(f"❌ [CW] Erro ao criar contato: {text}")
                        return None

                    data = await resp.json()
                    source_id = data.get("source_id") or data.get("contact_identifier")

                    if not source_id:
                        logger.error(f"⚠️ Contato criado sem source_id: {data}")
                    else:
                        logger.info(f"[CW] Contato OK id={source_id}")

                    return source_id

        except Exception as e:
            logger.error(f"❌ Exceção ao criar contato: {e}")
            return None

    # --------------------------------------------------------
    # Buscar conversa aberta
    # --------------------------------------------------------
    async def get_open_conversation(self, inbox_identifier: str, contact_identifier: str) -> Optional[str]:

        url = (
            f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/"
            f"contacts/{contact_identifier}/conversations"
        )

        logger.info(f"[CW] get_open_conversation → {contact_identifier}")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._headers()) as resp:
                    text = await resp.text()

                    if resp.status != 200:
                        return None

                    convs = await resp.json()

                    if isinstance(convs, list):
                        for c in convs:
                            if c.get("status") == "open":
                                cid = str(c.get("id"))
                                logger.info(f"[CW] Conversa aberta={cid}")
                                return cid

        except Exception as e:
            logger.warning(f"⚠️ Erro buscando conversa: {e}")

        return None

    # --------------------------------------------------------
    # Criar conversa
    # --------------------------------------------------------
    async def create_conversation(self, inbox_identifier: str, contact_identifier: str) -> Optional[str]:

        url = (
            f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/"
            f"contacts/{contact_identifier}/conversations"
        )

        logger.info(f"[CW] Criando nova conversa para {contact_identifier}")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json={}, headers=self._headers()) as resp:

                    text = await resp.text()

                    if resp.status != 200:
                        logger.error(f"❌ Falha criar conversa: {text}")
                        return None

                    data = await resp.json()
                    return str(data.get("id"))

        except Exception as e:
            logger.error(f"❌ Erro criando conversa: {e}")
            return None

    # --------------------------------------------------------
    # Garantir contato + conversa usando Redis
    # --------------------------------------------------------
    async def ensure_contact_and_conversation(self, inbox_identifier: str, identifier: str, name: str):

        key_contact = f"cw:contact:{inbox_identifier}:{identifier}"
        key_conv = f"cw:conversation:{inbox_identifier}:{identifier}"

        cached_contact = await cache_get(key_contact)
        cached_conv = await cache_get(key_conv)

        if cached_contact and cached_conv:
            logger.info(f"[CW] Cache HIT contact={cached_contact}, conv={cached_conv}")
            return cached_contact, cached_conv

        logger.info(f"[CW] Cache MISS — criando contato e conversa ({identifier})")

        # Criar ou pegar contato
        contact_identifier = await self.create_contact(inbox_identifier, identifier, name)
        if not contact_identifier:
            return None, None

        # Tentar conversa aberta
        conv_id = await self.get_open_conversation(inbox_identifier, contact_identifier)
        if not conv_id:
            conv_id = await self.create_conversation(inbox_identifier, contact_identifier)

        ttl = 60 * 60 * 24 * 30  # 30 dias
        await cache_set(key_contact, contact_identifier, ttl_seconds=ttl)
        await cache_set(key_conv, conv_id, ttl_seconds=ttl)

        return contact_identifier, conv_id

    # --------------------------------------------------------
    # Envio texto → Chatwoot
    # --------------------------------------------------------
    async def send_text_message(
        self,
        inbox_identifier,
        contact_identifier,
        conversation_id,
        message: str,
    ):
        url = (
            f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/"
            f"contacts/{contact_identifier}/conversations/{conversation_id}/messages"
        )

        message = "" if message is None else str(message)

        payload = {"content": message}

        logger.info(f"[CW] Enviando texto → {message}")
        logger.info(f"[CW] URL={url}")
        logger.info(f"[CW] Payload={payload}")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=payload, headers=self._headers()) as resp:
                body = await resp.text()
                logger.error(f"[CW RESPONSE TEXT] status={resp.status} body={body}")

                return {"status": resp.status, "response": body}


    # --------------------------------------------------------
    # Envio mídia → Chatwoot
    # --------------------------------------------------------
    async def send_media_message(
        self, inbox_identifier, contact_identifier, conversation_id, file_url, caption: Optional[str] = None
    ):

        logger.info(f"[CW] Enviando mídia → {file_url}")

        file_data = await self._download_file(file_url)
        if not file_data:
            logger.error("[CW] Falha ao baixar mídia antes de enviar")
            return {"error": "failed_to_download"}

        filename, file_bytes, mime = file_data
        file_bytes.seek(0)

        url = (
            f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/"
            f"contacts/{contact_identifier}/conversations/{conversation_id}/messages"
        )

        form = aiohttp.FormData()
        form.add_field("attachments[]", file_bytes, filename=filename, content_type=mime)

        caption = (caption or "").strip()
        if caption:
            form.add_field("content", caption)

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, data=form, headers=self._headers()) as resp:
                text = await resp.text()
                logger.info(f"[CW] send_media_message status={resp.status} body={text}")
                return {"status": resp.status, "response": text}

    # ============================================================
    # FUNÇÃO PRINCIPAL — ZAPI → CHATWOOT
    # ============================================================
    async def send_from_zapi_payload(self, payload: Dict[str, Any], inbox_identifier: str):

        raw_identifier = payload.get("phone") or ""
        is_group = payload.get("isGroup", False) or raw_identifier.endswith("-group")

        if is_group:
            identifier = raw_identifier            # ex: 120363405169721246-group
            name = payload.get("chatName") or "Grupo WhatsApp"
        else:
            identifier = self._normalize_phone(raw_identifier)
            name = payload.get("senderName") or "Cliente"

        msg_type = detect_zapi_message_type(payload)

        logger.info(f"[CW] ZAPI → CW id={identifier} tipo={msg_type} grupo={is_group}")

        if not identifier:
            logger.warning("[CW] Sem identificador válido — ignorado")
            return {"ignored": True}

        # Garantir contato + conversa
        contact_identifier, conversation_id = await self.ensure_contact_and_conversation(
            inbox_identifier, identifier, name
        )

        if not contact_identifier or not conversation_id:
            logger.error("[CW] Falha ao preparar contato/conversa")
            return {"error": "failed_to_prepare_contact_or_conversation"}

        # ---------------- TEXTO ----------------
        if msg_type == "text":
            text = payload.get("text", {}).get("message") or ""

            if is_group:
                sender = payload.get("senderName") or "Desconhecido"
                text = f"**{sender}:**\n\n{text}"

            return await self.send_text_message(
                inbox_identifier, contact_identifier, conversation_id, text
            )

        # ---------------- MÍDIA ----------------
        if msg_type in ["image", "video", "audio", "document"]:
            media = payload.get(msg_type) or {}
            
            # --- DEBUG FORCE BRUTE (PRINT) ---
            import json
            try:
                print(f"\n>>> [DEBUG] MEDIA DICT: {json.dumps(media, default=str)}")
            except:
                print(f"\n>>> [DEBUG] MEDIA DICT (RAW): {media}")
            # ---------------------------------

            url_map = {
                "image": "imageUrl",
                "video": "videoUrl",
                "audio": "audioUrl",
                "document": "documentUrl",
            }

            file_url = media.get(url_map.get(msg_type, ""))

            # Tentativa 1: Legenda da Mídia
            caption_from_media = media.get("caption")
            
            # Tentativa 2: Legenda do Texto
            caption_from_text = payload.get("text", {}).get("message") if payload.get("text") else None
            
            # Decisão Final
            raw_caption = caption_from_media
            if not raw_caption:
                raw_caption = caption_from_text
            
            raw_caption = raw_caption or ""

            # --- DEBUG VARIAVEIS (PRINT) ---
            print(f">>> [DEBUG] CAPTIONS -> FromMedia: '{caption_from_media}' | FromText: '{caption_from_text}' | FINAL: '{raw_caption}'\n")
            # -------------------------------

            if is_group:
                sender = payload.get("senderName") or "Desconhecido"
                
                if raw_caption.strip():
                    caption = f"**{sender}:**\n\n{raw_caption}"
                else:
                    caption = f"**{sender}**"
            else:
                caption = raw_caption

            return await self.send_media_message(
                inbox_identifier, contact_identifier, conversation_id, file_url, caption=caption
            )

        logger.info("[CW] Tipo de mensagem desconhecido, ignorando")
        return {"ignored": True}


# Instância Global
chatwoot_client = ChatwootClient()
