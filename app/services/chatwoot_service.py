# file: app/services/chatwoot_service.py

import logging
import re
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import aiohttp

from app.core.settings import settings

logger = logging.getLogger("chatwoot_service")
logger.setLevel(logging.INFO)


class ChatwootError(Exception):
    pass


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


class ChatwootClient:
    def __init__(self) -> None:
        self.base_url = settings.CHATWOOT_BASE_URL.rstrip("/")
        self.api_key = settings.CHATWOOT_API_KEY
        self._conv_cache: dict[str, tuple[str | None, str | None]] = {}

        self.timeout = aiohttp.ClientTimeout(total=15)

        logger.info(f"[CW] Inicializando ChatwootClient base_url={self.base_url}")

        if not self.base_url:
            logger.error("❌ CHATWOOT_BASE_URL não definido.")
        if not self.api_key:
            logger.error("❌ CHATWOOT_API_KEY não definido.")

    # =======================================
    # HEADERS
    # =======================================
    def _headers(self) -> Dict[str, str]:
        return {"api_access_token": self.api_key}

    # =======================================
    # Normalização telefone
    # =======================================
    @staticmethod
    def _normalize_phone(phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        digits = re.sub(r"\D", "", str(phone))
        return digits if digits.startswith("+") else f"+{digits}"

    # =======================================
    # Download de mídia
    # =======================================
    async def _download_file(self, url: str) -> Optional[tuple[str, BytesIO, str]]:
        logger.info(f"[CW] Iniciando download de mídia: {url}")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as resp:
                    logger.info(f"[CW] Status download mídia: {resp.status}")

                    if resp.status != 200:
                        logger.warning(f"⚠️ [CW] Falha ao baixar arquivo: status={resp.status}")
                        return None

                    content = await resp.read()
                    content_type = resp.headers.get("Content-Type", "application/octet-stream")
                    filename = url.split("/")[-1] or "arquivo"

                    return filename, BytesIO(content), content_type

        except Exception as e:
            logger.error(f"❌ [CW] Erro ao baixar arquivo: {e}")
            return None

    # =======================================
    # Criar contato
    # =======================================
    async def create_contact(self, inbox_identifier: str, phone: str, name: str) -> Optional[str]:
        url = f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/contacts"
        payload = {
            "identifier": phone,
            "name": name,
            "phone_number": phone,
        }

        logger.info(f"[CW] create_contact inbox={inbox_identifier} phone={phone} name={name}")
        logger.info(f"[CW] POST {url}")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=self._headers()) as resp:
                    text = await resp.text()
                    logger.info(f"[CW] create_contact status={resp.status} body={text}")

                    if resp.status != 200:
                        logger.error(
                            f"❌ [CW] Erro ao criar contato "
                            f"(status={resp.status}) url={url} body={text}"
                        )
                        return None

                    try:
                        data = await resp.json()
                    except Exception:
                        logger.error(f"❌ [CW] Resposta inválida ao criar contato: {text}")
                        return None

                    source_id = data.get("source_id") or data.get("contact_identifier")
                    if not source_id:
                        logger.error(f"⚠️ [CW] Contato criado sem source_id: {data}")
                    else:
                        logger.info(f"[CW] Contato criado/obtido contact_identifier={source_id}")

                    return source_id
        except Exception as e:
            logger.error(f"❌ [CW] Exceção ao criar contato: {e}")
            return None

    # =======================================
    # Buscar conversa aberta
    # =======================================
    async def get_open_conversation(self, inbox_identifier: str, contact_identifier: str) -> Optional[str]:
        url = (
            f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/"
            f"contacts/{contact_identifier}/conversations"
        )

        logger.info(f"[CW] get_open_conversation inbox={inbox_identifier} contact={contact_identifier}")
        logger.info(f"[CW] GET {url}")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._headers()) as resp:

                    text = await resp.text()
                    logger.info(f"[CW] get_open_conversation status={resp.status} body={text}")

                    if resp.status != 200:
                        return None

                    try:
                        convs = await resp.json()
                    except Exception:
                        logger.error(f"❌ [CW] Resposta inválida em get_open_conversation: {text}")
                        return None

                    if isinstance(convs, list):
                        for c in convs:
                            if c.get("status") == "open":
                                cid = str(c.get("id"))
                                logger.info(f"[CW] Conversa aberta encontrada id={cid}")
                                return cid
        except Exception as e:
            logger.warning(f"⚠️ [CW] Falha ao obter conversas: {e}")
        return None

    # =======================================
    # Criar conversa
    # =======================================
    async def create_conversation(self, inbox_identifier: str, contact_identifier: str) -> Optional[str]:
        url = (
            f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/"
            f"contacts/{contact_identifier}/conversations"
        )

        logger.info(f"[CW] create_conversation inbox={inbox_identifier} contact={contact_identifier}")
        logger.info(f"[CW] POST {url}")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json={}, headers=self._headers()) as resp:
                    text = await resp.text()
                    logger.info(f"[CW] create_conversation status={resp.status} body={text}")

                    if resp.status != 200:
                        logger.error(
                            f"❌ [CW] Erro ao criar conversa "
                            f"(status={resp.status}) url={url} body={text}"
                        )
                        return None

                    try:
                        data = await resp.json()
                    except Exception:
                        logger.error(f"❌ [CW] Resposta inválida em create_conversation: {text}")
                        return None

                    cid = str(data.get("id")) if data.get("id") else None
                    logger.info(f"[CW] Conversa criada id={cid}")
                    return cid
        except Exception as e:
            logger.error(f"❌ [CW] Erro ao criar conversa: {e}")
            return None

    # =======================================
    # Garantir contato + conversa
    # =======================================
    async def ensure_contact_and_conversation(
        self,
        inbox_identifier: str,
        phone: str,
        name: str
    ) -> Tuple[str | None, str | None]:

        cache_key = f"{inbox_identifier}:{phone}"

        if cache_key in self._conv_cache:
            c1, c2 = self._conv_cache[cache_key]
            if c1 and c2:
                logger.info(f"[CW] Cache hit contact={c1} conv={c2}")
                return c1, c2

        logger.info(f"[CW] ensure_contact_and_conversation inbox={inbox_identifier} phone={phone}")

        contact_identifier = await self.create_contact(inbox_identifier, phone, name)
        if not contact_identifier:
            logger.error("[CW] Falha ao garantir contato, abortando")
            return None, None

        conv_id = await self.get_open_conversation(inbox_identifier, contact_identifier)

        if not conv_id:
            logger.info("[CW] Nenhuma conversa aberta, criando nova")
            conv_id = await self.create_conversation(inbox_identifier, contact_identifier)

        self._conv_cache[cache_key] = (contact_identifier, conv_id)

        return contact_identifier, conv_id

    # =======================================
    # Envio texto
    # =======================================
    async def send_text_message(
        self,
        inbox_identifier: str,
        contact_identifier: str,
        conversation_id: str,
        message: str,
        echo_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        url = (
            f"{self.base_url}/public/api/v1/inboxes/{inbox_identifier}/"
            f"contacts/{contact_identifier}/conversations/{conversation_id}/messages"
        )

        payload = {"content": message}
        if echo_id:
            payload["echo_id"] = echo_id

        logger.info(
            f"[CW] send_text_message inbox={inbox_identifier} contact={contact_identifier} "
            f"conv={conversation_id} echo_id={echo_id}"
        )
        logger.info(f"[CW] POST {url} payload={payload}")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=payload, headers=self._headers()) as resp:
                text = await resp.text()
                logger.info(f"[CW] send_text_message status={resp.status} body={text}")
                return {"status": resp.status, "response": text}

    # =======================================
    # Envio mídia
    # =======================================
    async def send_media_message(
        self,
        inbox_identifier: str,
        contact_identifier: str,
        conversation_id: str,
        file_url: str,
        caption: Optional[str] = None,
        echo_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"[CW] send_media_message inbox={inbox_identifier} contact={contact_identifier} "
            f"conv={conversation_id} file_url={file_url} echo_id={echo_id}"
        )

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
        if caption:
            form.add_field("content", caption)
        if echo_id:
            form.add_field("echo_id", echo_id)

        logger.info(f"[CW] POST (media) {url} caption={caption} mime={mime}")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, data=form, headers=self._headers()) as resp:
                text = await resp.text()
                logger.info(f"[CW] send_media_message status={resp.status} body={text}")
                return {"status": resp.status, "response": text}

    # =======================================
    # Função principal
    # =======================================
    async def send_from_zapi_payload(
        self,
        payload: Dict[str, Any],
        inbox_identifier: str
    ) -> Dict[str, Any]:

        raw_phone = payload.get("participantPhone") if payload.get("isGroup") else payload.get("phone")
        phone = self._normalize_phone(raw_phone)
        name = payload.get("senderName") or payload.get("chatName") or "Cliente"

        msg_type = detect_zapi_message_type(payload)
        message_id = payload.get("messageId")

        logger.info(
            f"[CW] send_from_zapi_payload inbox={inbox_identifier} phone={phone} "
            f"name={name} msg_type={msg_type} message_id={message_id}"
        )

        if not phone:
            logger.warning("[CW] Payload sem telefone, ignorando")
            return {"ignored": True, "reason": "missing_phone"}

        contact_identifier, conversation_id = await self.ensure_contact_and_conversation(
            inbox_identifier,
            phone,
            name
        )

        if not contact_identifier or not conversation_id:
            logger.error("[CW] Falha ao preparar contato ou conversa")
            return {"error": "failed_to_prepare_contact_or_conversation"}

        # TEXTO
        if msg_type == "text":
            text = payload.get("text", {}).get("message")
            if not text:
                logger.info("[CW] Mensagem de texto vazia, ignorando")
                return {"ignored": True}
            return await self.send_text_message(
                inbox_identifier,
                contact_identifier,
                conversation_id,
                text,
                echo_id=message_id
            )

        # MÍDIA
        if msg_type in ["image", "video", "audio", "document"]:
            media = payload.get(msg_type) or {}
            url_map = {
                "image": "imageUrl",
                "video": "videoUrl",
                "audio": "audioUrl",
                "document": "documentUrl",
            }
            file_url = media.get(url_map.get(msg_type, ""))

            caption = payload.get("text", {}).get("message") or media.get("caption")

            return await self.send_media_message(
                inbox_identifier,
                contact_identifier,
                conversation_id,
                file_url,
                caption=caption,
                echo_id=message_id
            )

        logger.info("[CW] Tipo de mensagem desconhecido, ignorando")
        return {"ignored": True}


chatwoot_client = ChatwootClient()
