"""
Network Protocol Visualizer — FastAPI application entry point.
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import browse, mail, stream

app = FastAPI(
    title="Network Protocol Visualizer",
    description="Dual-panel dashboard for visualizing DNS, HTTP, and SMTP protocols",
    version="1.0.0",
)

# ── CORS (allow frontend served from any localhost port or file://)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers
app.include_router(browse.router)
app.include_router(mail.router)
app.include_router(stream.router)

# ── Static files (frontend)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main frontend HTML."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h1>Frontend not found — run from project root</h1>")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
