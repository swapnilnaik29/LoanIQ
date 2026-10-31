"""
Main FastAPI Application Entry Point for LoanIQ.
Integrates REST APIs, MCP Server, SQLite state, and serves the Frontend interface.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.database import init_db
from backend.routers.system import system_router
from backend.routers.auth import auth_router
from backend.routers.merchants import merchants_router
from backend.routers.loans import loans_router
from backend.routers.assistant import assistant_router
from backend.routers.translation import translation_router
from backend.mcp.server import mcp_router

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and tables
    init_db()
    print("LoanIQ database initialized.")
    yield


app = FastAPI(
    title="LoanIQ API & MCP Service",
    description="Merchant-facing AI-powered credit recommendation, cashflow forecasting, and loan optimization application.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST Routers under /api
app.include_router(system_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(merchants_router, prefix="/api")
app.include_router(loans_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")
app.include_router(translation_router, prefix="/api")

# Include MCP Routers
app.include_router(mcp_router, prefix="/api")
app.include_router(mcp_router, prefix="")

# Mount Frontend static assets
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    if (FRONTEND_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/")
    def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/login")
    def serve_login():
        return FileResponse(str(FRONTEND_DIR / "login.html"))

