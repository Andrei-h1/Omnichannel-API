import boto3
from botocore.client import Config
import uuid
import mimetypes

from app.core.settings import settings

session = boto3.session.Session()

r2 = session.client(
    service_name='s3',
    endpoint_url=settings.R2_ENDPOINT,   # ex: https://8400ab189d13...r2.cloudflarestorage.com
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=Config(signature_version='s3v4')
)

BUCKET = "omnichannel-media"


def upload_bytes_to_r2(content: bytes, filename: str | None = None, mime: str | None = None) -> str:
    """Faz upload de bytes ao R2 e retorna URL pública"""
    if not filename:
        ext = mimetypes.guess_extension(mime) or ".bin"
        filename = f"{uuid.uuid4()}{ext}"

    r2.put_object(
        Bucket=BUCKET,
        Key=filename,
        Body=content,
        ContentType=mime or "application/octet-stream",
    )

    # Public URL automaticamente disponível
    return f"{settings.R2_PUBLIC_URL}/{filename}"
