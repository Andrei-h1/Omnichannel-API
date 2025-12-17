# file: app/api/v1/bot_sessions.py

import logging
from fastapi import APIRouter, Query, Response, status
from fastapi.responses import JSONResponse

from app.schemas.bot_sessions import BotSessionRead, BotSessionCreate
from app.services.bot_sessions_service import create_bot_session
from app.services.bot_sessions_cache import get_active_bot_session

router = APIRouter()
logger = logging.getLogger("bot_session")
logger.setLevel(logging.INFO)


@router.get(
    "/active",
    response_model=BotSessionRead,
)
async def get_active_bot_session_endpoint(
    conversation_id: str = Query(...),
):
    logger.info(f"[BotSession] Consulta sessão ativa: conversation_id={conversation_id}")

    session = await get_active_bot_session(conversation_id)

    if session is None:
        logger.info("[BotSession] Nenhuma sessão ativa encontrada")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=None,
        )
    
    print(
        f"[DEBUG] type(session)={type(session)} value={session}"
    )


    logger.info(f"[BotSession] Sessão ativa encontrada: session_id={session.session_id}")
    return session


@router.post(
    "",
    response_model=BotSessionRead,
)
async def create_bot_session_endpoint(payload: BotSessionCreate):
    logger.info(
        f"[BotSession] Create request: conversation_id={payload.conversation_id}"
    )

    session = await create_bot_session(payload)

    return session