from datetime import datetime, timezone
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api.router import api_router

def create_app() -> FastAPI:
    app = FastAPI(title="CRISPR Backend", version="0.1.0")

    allowed = os.getenv("ALLOWED_ORIGINS", "")
    allow_origins = [o.strip() for o in allowed.split(",") if o.strip()]
    if not allow_origins:
        # fallback for local dev if env not set
        allow_origins = ["http://localhost:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trust Cloudflare tunnel + nginx proxy forwarded headers
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

    app.include_router(api_router, prefix="/api")

    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "backend"
        }

    return app

app = create_app()
