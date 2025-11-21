# file: app/utils/file_proxy.py

import uuid
import logging
import mimetypes
import requests

from boto3.session import Session
from botocore.client import Config

from app.core.settings import settings

logger = logging.getLogger("file_proxy")


# ==========================================================
# 🔧 Configuração do Cloudflare R2
# ==========================================================

session = Session()

r2 = session.client(
    service_name="s3",
    endpoint_url=settings.R2_ENDPOINT,
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
)

BUCKET = "omnichannel-media"


# ==========================================================
# 📤 Upload direto (bytes -> R2)
# ==========================================================
def upload_bytes_to_r2(content: bytes, mime: str) -> str:
    """
    Envia bytes diretamente para o R2 e retorna a URL pública.
    """

    ext = mimetypes.guess_extension(mime) or ".bin"
    filename = f"{uuid.uuid4()}{ext}"

    try:
        r2.put_object(
            Bucket=BUCKET,
            Key=filename,
            Body=content,
            ContentType=mime,
        )
    except Exception as e:
        logger.error(f"❌ [file_proxy] Erro enviando arquivo ao R2: {e}")
        raise

    public_url = f"{settings.R2_PUBLIC_URL}/{filename}"

    logger.info(f"[file_proxy] Upload R2 OK → {public_url}")
    return public_url


# ==========================================================
# 📥 Download remoto + upload direto ao R2
#    (Chatwoot → Middleware → WhatsApp)
# ==========================================================
async def download_and_push_to_r2(url: str) -> tuple[str, str]:
    """
    Baixa a mídia remota (do Chatwoot), faz upload imediato ao R2
    e retorna (url_publica, mime).
    """
    logger.info(f"[file_proxy] Baixando e enviando ao R2: {url}")

    try:
        resp = requests.get(url, stream=True, timeout=25)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        content = resp.content
        mime = resp.headers.get("Content-Type", "application/octet-stream")

    except Exception as e:
        logger.error(f"❌ [file_proxy] Erro baixando mídia: {e}")
        raise

    public_url = upload_bytes_to_r2(content, mime)

    return public_url, mime
