# file: app/utils/file_proxy.py

import os
import uuid
import aiofiles
import logging
import mimetypes
import requests
from datetime import datetime, timedelta, timezone

from boto3.session import Session
from botocore.client import Config

from app.core.settings import settings

logger = logging.getLogger("file_proxy")


# ==========================================================
# 🔧 Diretório cross-platform (CACHE LOCAL)
# ==========================================================
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "omni_files")
)
os.makedirs(BASE_DIR, exist_ok=True)

FILE_TTL_MINUTES = 30


# ==========================================================
# 🔧 Configuração do R2 (Cloudflare)
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


def upload_bytes_to_r2(content: bytes, mime: str) -> str:
    """
    Faz upload de bytes ao Cloudflare R2 e retorna a URL pública.
    """

    ext = mimetypes.guess_extension(mime) or ".bin"
    filename = f"{uuid.uuid4()}{ext}"

    r2.put_object(
        Bucket=BUCKET,
        Key=filename,
        Body=content,
        ContentType=mime,
    )

    public_url = f"{settings.R2_PUBLIC_URL}/{filename}"

    logger.info(f"[file_proxy] R2 upload OK → {public_url}")
    return public_url


# ==========================================================
# 📥 A) DOWNLOAD PARA CACHE LOCAL
#     (WhatsApp → Middleware → Chatwoot)
#     — Mantido exatamente igual
# ==========================================================
async def download_and_cache_file(url: str) -> tuple[str, str]:
    print("⚪ Entrou no download_and_cache_file", url)

    try:
        r = requests.get(url, stream=True, timeout=20)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")

        content_type = r.headers.get("Content-Type", "application/octet-stream")

    except Exception as e:
        logger.error(f"[file_proxy] Erro ao baixar arquivo: {e}")
        raise

    file_id = str(uuid.uuid4())
    ext = mimetypes.guess_extension(content_type) or ".bin"
    local_path = os.path.join(BASE_DIR, f"{file_id}{ext}")

    try:
        async with aiofiles.open(local_path, "wb") as f:
            await f.write(r.content)

        logger.info(f"[file_proxy] Cached OK: {local_path}")

    except Exception as e:
        logger.error(f"[file_proxy] Erro salvando {local_path}: {e}")
        raise

    return file_id, content_type


# ==========================================================
# 📥 B) DOWNLOAD + UPLOAD IMEDIATO PARA R2
#     (Chatwoot → Middleware → WhatsApp)
# ==========================================================
async def download_and_push_to_r2(url: str) -> tuple[str, str]:
    """
    Baixa um arquivo remoto (via Chatwoot) e envia ao R2.
    Retorna (public_url, mime_type).
    """
    logger.info(f"[file_proxy] Baixando para R2: {url}")

    try:
        r = requests.get(url, stream=True, timeout=20)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")

        content = r.content
        mime = r.headers.get("Content-Type", "application/octet-stream")

    except Exception as e:
        logger.error(f"[file_proxy] Erro ao baixar arquivo p/ R2: {e}")
        raise

    # 👉 Upload direto para o Cloudflare R2
    public_url = upload_bytes_to_r2(content, mime)

    return public_url, mime


# ==========================================================
# 📤 Get local path (para Chatwoot)
# ==========================================================
def get_local_file_path(file_id: str) -> str | None:
    try:
        for fname in os.listdir(BASE_DIR):
            if fname.startswith(file_id):
                return os.path.join(BASE_DIR, fname)
    except Exception as e:
        logger.error(f"[file_proxy] Erro ao listar arquivos: {e}")

    return None


# ==========================================================
# 🧹 Limpeza de arquivos expirados
# ==========================================================
def clean_expired_files():
    now = datetime.now(timezone.utc)

    for fname in os.listdir(BASE_DIR):
        fpath = os.path.join(BASE_DIR, fname)

        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc)

            if now - mtime > timedelta(minutes=FILE_TTL_MINUTES):
                os.remove(fpath)
                logger.info(f"[file_proxy] Removed expired: {fname}")

        except Exception:
            pass
