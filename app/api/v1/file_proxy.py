# file: app/api/v1/file_proxy.py

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.utils.file_proxy import (
    get_local_file_path,
    clean_expired_files
)

router = APIRouter()
logger = logging.getLogger("file_proxy_api")


@router.get("/{file_id}")
async def serve_file(file_id: str):
    """
    Exponibiliza arquivos temporários.
    Exemplo: GET /v1/files/<file_id>
    """
    print("🔥 CHEGOU REQUISIÇÃO CHATWOOT")

    # Remove arquivos vencidos
    clean_expired_files()

    path = get_local_file_path(file_id)
    if not path:
        raise HTTPException(status_code=404, detail="file_not_found")
    
    return FileResponse(path)
