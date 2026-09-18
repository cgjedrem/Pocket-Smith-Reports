"""FastAPI app — PS sync API. Slice 2: all routers mounted."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from budget_api.routers import (
    accounts,
    bills,
    categories,
    category_mappings,
    mega_reports,
    partners,
    reports,
    settings,
    status,
    sync,
)
from budget_api.services import storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sync status is in-memory process truth persisted to disk; a persisted
    # 'running' can only be stale at startup, so drop it. Terminal
    # success/failed statuses survive restarts (they carry sync history).
    storage.clear_stale_sync_status()
    yield


app = FastAPI(title="Pocket-Smith Reports API", version="0.1.0", lifespan=lifespan)


# Fix 1 — 422→400: flatten pydantic validation errors to first human-readable message.
# Fixes AC10/AC14/AC23 at framework level. All pydantic errors → 400 {detail: string}.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = " -> ".join(str(l) for l in first.get("loc", []))
        msg = first.get("msg", "validation error")
        detail = f"{loc}: {msg}" if loc else msg
    else:
        detail = "validation error"
    return JSONResponse(status_code=400, content={"detail": detail})


# CORS allows browser cross-origin requests from local dev servers.
# Network exposure is controlled by binding uvicorn to 127.0.0.1 (see run script).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


# Routers — prefix composed with each router's own path.
app.include_router(sync.router, prefix="/api")  # /api/sync
app.include_router(status.router, prefix="/api/sync")  # /api/sync/status
app.include_router(partners.router, prefix="/api")  # /api/partners
app.include_router(accounts.router, prefix="/api")  # /api/accounts
app.include_router(settings.router, prefix="/api/settings")  # /api/settings/api-key
app.include_router(categories.router, prefix="/api")  # /api/categories
app.include_router(reports.router, prefix="/api")  # /api/reports/*
app.include_router(mega_reports.router, prefix="/api")  # /api/mega-reports/*
app.include_router(category_mappings.router, prefix="/api")  # /api/category-mappings
app.include_router(bills.router, prefix="/api")  # /api/bills/dashboard


# Bills router — no-store on /api/bills/dashboard + /api/bills/dashboard/events
# + /api/bills/dashboard/event.
# HTTPException handler strips response.headers, so set via middleware on the way out.
# Explicit allow-list: any future /api/bills/* gets caching by default (safer).
_NO_STORE_PATHS = frozenset(
    {
        "/api/bills/dashboard",
        "/api/bills/dashboard/events",
        "/api/bills/dashboard/event",
    }
)


@app.middleware("http")
async def _bills_no_store(request, call_next):
    response = await call_next(request)
    if request.url.path in _NO_STORE_PATHS:
        response.headers["Cache-Control"] = "no-store"
    return response
