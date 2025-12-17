from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/omnichannel.db"
    PUBLIC_BASE_URL: str = "https://d45fcae8f56f.ngrok-free.app"
    REDIS_URL: str = "redis://localhost:6379/0"

    CHATWOOT_BASE_URL: str = "https://app.chatwoot.com"
    CHATWOOT_API_KEY: str = "jP1KcU4VQnijEzWNsm48F49t"
    CHATWOOT_INBOX_IDENTIFIER: str = "UiZjygWEE1ptqRRrdX68WfTm"

    ZAPI_BASE_URL: str = "https://api.z-api.io"
    ZAPI_CLIENT_TOKEN: str = "" 

    R2_ENDPOINT: str = "https://8400ab189d13fab90d0caef1276f12f3.r2.cloudflarestorage.com"
    R2_ACCESS_KEY_ID: str = "751fa789dd22a05cd89b99e00bfac13b"
    R2_SECRET_ACCESS_KEY: str = "1a6a681e57704fa5eb347dbf8b888716753e2d92352af2558bb48c4c3eb3abb9"
    R2_PUBLIC_URL: str ="https://pub-bcf5d9058db24b4ca15b08c02cf24317.r2.dev"

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
