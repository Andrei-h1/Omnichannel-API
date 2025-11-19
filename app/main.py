from fastapi import FastAPI
from app.api.v1 import api_router

app = FastAPI(title="Omnichannel API", version="1.0.0")

app.include_router(api_router, prefix="/v1")

@app.get("/health")
def health():
    return {"status": "ok"}