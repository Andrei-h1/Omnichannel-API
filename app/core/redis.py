# file: app/core/redis.py

import redis.asyncio as aioredis
import logging
from app.core.settings import settings

logger = logging.getLogger("redis")

# ============================================================
# 🔌 Conexão Redis — Singleton
# ============================================================

redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """
    Retorna um cliente Redis reutilizável (singleton).
    """
    global redis_client

    if redis_client is None:
        try:
            redis_client = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                db=0,
                decode_responses=True,  # sempre strings, facilita
            )

            # Testa conexão
            pong = await redis_client.ping()
            if pong:
                logger.info("⚡ Redis conectado com sucesso!")

        except Exception as e:
            logger.error(f"❌ Erro conectando ao Redis: {e}")
            raise

    return redis_client


# ============================================================
# 🧩 Helpers de Cache
# ============================================================

async def cache_set(key: str, value: str, ttl_seconds: int | None = None):
    """
    Salva no Redis com TTL opcional.
    """
    redis = await get_redis()

    try:
        await redis.set(key, value)
        if ttl_seconds:
            await redis.expire(key, ttl_seconds)
        logger.debug(f"[redis] SET {key} = {value} (ttl={ttl_seconds})")

    except Exception as e:
        logger.error(f"❌ Erro no cache_set({key}): {e}")


async def cache_get(key: str) -> str | None:
    """
    Recupera chave do Redis.
    """
    redis = await get_redis()

    try:
        value = await redis.get(key)
        logger.debug(f"[redis] GET {key} -> {value}")
        return value
    except Exception as e:
        logger.error(f"❌ Erro no cache_get({key}): {e}")
        return None


async def cache_delete(key: str):
    """
    Remove uma chave do Redis.
    """
    redis = await get_redis()

    try:
        await redis.delete(key)
        logger.debug(f"[redis] DEL {key}")
    except Exception as e:
        logger.error(f"❌ Erro no cache_delete({key}): {e}")
