# file: app/services/zapi_service.py

import logging
import requests
from app.core.settings import settings

logger = logging.getLogger("zapi_service")


class ZAPIError(Exception):
    pass


class ZAPIClient:
    def __init__(self):
        self.base_url = settings.ZAPI_BASE_URL.rstrip("/")
        self.client_token = settings.ZAPI_CLIENT_TOKEN
        self.timeout = 20
        self.session = requests.Session()

    # =========================================================================
    # 🔵 A) ENVIO GENÉRICO VIA JSON (para texto e URLs)
    # =========================================================================
    def _post_json(self, instance_id: str, token: str, endpoint: str, payload: dict):
        url = f"{self.base_url}/instances/{instance_id}/token/{token}{endpoint}"

        logger.warning("====== ZAPI DEBUG OUT ======")
        logger.warning(f"URL: {url}")
        logger.warning(f"Headers: {{'Client-Token': '{self.client_token}'}}")
        logger.warning(f"Payload: {payload}")

        try:
            r = self.session.post(
                url,
                json=payload,
                headers={"Client-Token": self.client_token},
                timeout=self.timeout,
            )

            logger.warning("====== ZAPI DEBUG IN ======")
            logger.warning(f"Status: {r.status_code}")
            logger.warning(f"Response text: {r.text}")

            if r.status_code >= 400:
                raise ZAPIError(r.text)

            return r.json()

        except Exception as e:
            logger.exception("❌ ERROR sending to Z-API")
            raise ZAPIError(str(e)) from e

    # =========================================================================
    # 🟣 B) ENVIO VIA MULTIPART (bytes)
    # =========================================================================
    def _post_multipart(self, instance_id: str, token: str, endpoint: str, files: dict, data: dict):
        """
        Z-API aceita envio de mídia via multipart/form-data
        quando enviamos arquivos como bytes.

        files = { "file": ("nome.ext", bytes, "mime/type") }
        data  = { campos adicionais }
        """

        url = f"{self.base_url}/instances/{instance_id}/token/{token}{endpoint}"

        logger.warning("====== ZAPI MULTIPART OUT ======")
        logger.warning(f"URL: {url}")
        logger.warning(f"Data: {data}")
        logger.warning(f"Files: {list(files.keys())}")

        try:
            r = self.session.post(
                url,
                data=data,
                files=files,
                headers={"Client-Token": self.client_token},
                timeout=self.timeout,
            )

            logger.warning("====== ZAPI MULTIPART IN ======")
            logger.warning(f"Status: {r.status_code}")
            logger.warning(f"Response: {r.text}")

            if r.status_code >= 400:
                raise ZAPIError(r.text)

            return r.json()

        except Exception as e:
            logger.exception("❌ ERROR sending multipart to Z-API")
            raise ZAPIError(str(e)) from e

    # =========================================================================
    # 📩 TEXTO
    # =========================================================================
    def send_text(self, instance_id: str, token: str, phone: str, message: str):
        return self._post_json(instance_id, token, "/send-text", {
            "phone": phone,
            "message": message
        })

    # =========================================================================
    # 🖼️ ENVIO DE MÍDIA VIA BYTES (recomendado)
    # =========================================================================
    def send_image_bytes(self, instance_id: str, token: str, phone: str, file_bytes: bytes, filename: str, mime: str, caption=""):
        files = {
            "image": (filename, file_bytes, mime)
        }
        data = {
            "phone": phone,
            "caption": caption or ""
        }
        return self._post_multipart(instance_id, token, "/send-image", files, data)

    def send_video_bytes(self, instance_id: str, token: str, phone: str, file_bytes: bytes, filename: str, mime: str, caption=""):
        files = {
            "video": (filename, file_bytes, mime)
        }
        data = {
            "phone": phone,
            "caption": caption or ""
        }
        return self._post_multipart(instance_id, token, "/send-video", files, data)

    def send_audio_bytes(self, instance_id: str, token: str, phone: str, file_bytes: bytes, filename: str, mime: str):
        files = {
            "audio": (filename, file_bytes, mime)
        }
        data = {
            "phone": phone
        }
        return self._post_multipart(instance_id, token, "/send-audio", files, data)

    def send_document_bytes(self, instance_id: str, token: str, phone: str, file_bytes: bytes, filename: str, mime: str, extension="pdf"):
        files = {
            "document": (filename, file_bytes, mime)
        }
        data = {
            "phone": phone
        }
        return self._post_multipart(instance_id, token, f"/send-document/{extension}", files, data)

    # =========================================================================
    # 🌐 ENVIO DE MÍDIA VIA URL (modo antigo)
    # =========================================================================
    def send_image(self, instance_id: str, token: str, phone: str, blob_url: str, caption=""):
        return self._post_json(instance_id, token, "/send-image", {
            "phone": phone,
            "image": blob_url,
            "caption": caption or ""
        })

    def send_video(self, instance_id: str, token: str, phone: str, blob_url: str, caption=""):
        return self._post_json(instance_id, token, "/send-video", {
            "phone": phone,
            "video": blob_url,
            "caption": caption or ""
        })

    def send_audio(self, instance_id: str, token: str, phone: str, blob_url: str):
        return self._post_json(instance_id, token, "/send-audio", {
            "phone": phone,
            "audio": blob_url
        })

    def send_document(self, instance_id: str, token: str, phone: str, blob_url: str, extension="pdf"):
        return self._post_json(instance_id, token, f"/send-document/{extension}", {
            "phone": phone,
            "document": blob_url
        })


# Instância global
zapi_client = ZAPIClient()
