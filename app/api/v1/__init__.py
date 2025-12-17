from fastapi import APIRouter

# Webhooks
from .webhooks_zapi import router as webhooks_zapi_router
from .webhooks_chatwoot import router as webhooks_chatwoot_router

# File Proxy
from .file_proxy import router as file_proxy_router

# BOT Endpoints
from .customers import router as customers_router
from .bot_sessions import router as bot_sessions_router

api_router = APIRouter()

# ========== Webhooks (funcionam agora) ==========
api_router.include_router(webhooks_zapi_router, prefix="/webhooks/zapi", tags=["webhooks"])
api_router.include_router(webhooks_chatwoot_router, prefix="/webhooks/chatwoot", tags=["webhooks"])

# ========== File Proxy ==========================
api_router.include_router(file_proxy_router, prefix="/files", tags=["proxy"])

# ========== BOT Endpoints =======================
api_router.include_router(customers_router, prefix="/customer", tags=["customers"])
api_router.include_router(bot_sessions_router, prefix="/bot_sessions", tags=["bot_sessions"])

# ========== CRUDs (ativaremos depois) ===========
# from .vendors import router as vendors_router
# from .conversations import router as conversations_router
# from .sessions import router as sessions_router
# from .messages import router as messages_router
#
# api_router.include_router(vendors_router, prefix="/vendors", tags=["vendors"])
# api_router.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
# api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
# api_router.include_router(messages_router, prefix="/messages", tags=["messages"])
