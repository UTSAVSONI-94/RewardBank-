"""RewardBank — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

import os
import sys

# Ensure root directory is in python path when running script directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from app.db import init_db
from app.routes.children import router as children_router
from app.routes.tasks import router as tasks_router
from app.routes.usage import router as usage_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="RewardBank",
        description="A ledger-based screen-time banking system",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["system"])
    def health():
        return {
            "status": "ok",
            "service": "RewardBank",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    app.include_router(tasks_router)
    app.include_router(usage_router)
    app.include_router(children_router)

    return app


# Create the app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    print("\n🏦 RewardBank server starting...")
    print("   Swagger docs: http://localhost:3000/docs")
    print("\n   Seeded users:")
    print("     Parent Alice: Bearer parent-token-alice")
    print("     Child  Bob:   Bearer child-token-bob")
    print("     Child  Charlie: Bearer child-token-charlie\n")

    uvicorn.run(app, host="0.0.0.0", port=3000)
