from fastapi import FastAPI
from api.router import api_router
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

def create_app() -> FastAPI:
    app = FastAPI(title="CRISPR Backend", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
