# file: app/api/v1/file_proxy.py

"""
Este módulo existia para servir arquivos locais temporários
para o Chatwoot, mas isso não é mais necessário.

Agora toda mídia é enviada diretamente ao Cloudflare R2,
que fornece URLs permanentes e públicas.

Portanto, este endpoint é mantido apenas para compatibilidade,
mas sempre retorna 410 (Gone).
"""

import logging
from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger("file_proxy_api")


@router.get("/{file_id}")
async def deprecated_file_proxy(file_id: str):
    """
    Endpoint desativado — o proxy de arquivos local não é mais utilizado.
    """
    logger.warning(
        f"[FILE_PROXY] Chamada recebida para file_id={file_id}, "
        "mas o sistema de arquivos local foi desativado."
    )

    raise HTTPException(
        status_code=410,
        detail="Este endpoint foi desativado. Mídias agora são servidas diretamente via Cloudflare R2."
    )
