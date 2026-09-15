"""FloodGuard AI — main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .config import settings
from .logging_conf import log
from .flood_engine import engine
from .services.pipeline import get_pipeline
from .api.routers.api_router import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting FloodGuard AI v{settings.app_version} — {settings.city_name}")
    # run an initial simulation (0-min baseline)
    try:
        engine.run(override_rainfall=30.0)
        log.info("Initial baseline run complete")
    except Exception as e:
        log.error(f"Initial baseline failed: {e}")
    # start the background pipeline
    pipeline = get_pipeline(engine)
    pipeline.start()
    yield
    pipeline.stop()
    log.info("FloodGuard AI shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Serve the frontend build from the root (for production mode)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIR):
    from starlette.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
