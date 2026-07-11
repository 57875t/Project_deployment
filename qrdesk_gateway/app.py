from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .provider import INSTRUMENTS, get_bundle

app = FastAPI(title="QR Desk Cloud Market Gateway", version="0.7.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/v1/market/health")
async def health() -> dict:
    providers = {
        "massive": bool(settings.massive_api_key),
        "eodhd": bool(settings.eodhd_api_token),
    }
    configured = [name for name, enabled in providers.items() if enabled]
    return {
        "ok": bool(configured),
        "status": "ok" if configured else "degraded",
        "provider": ", ".join(configured) if configured else "none",
        "entitlement": "configured" if configured else "missing",
        "openD": "not_required",
        "message": "Cloud market-data provider configured." if configured else "No cloud provider API key is configured.",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "instruments": len(INSTRUMENTS),
        "environment": settings.environment,
    }


@app.get("/v1/market/bundle")
async def bundle(
    instrument: str = Query(...),
    symbol: str = Query(""),
    range_key: str = Query("1mo", alias="range"),
    interval: str = Query("1h"),
    date: str = Query(""),
    extended: bool = Query(False),
) -> dict:
    if date:
        raise HTTPException(
            status_code=501,
            detail={
                "code": "HISTORICAL_DATE_NOT_IMPLEMENTED",
                "message": "Exact historical-date mode is not yet enabled in the cloud gateway.",
            },
        )
    if extended:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EXTENDED_UNSUPPORTED",
                "message": "Extended-hours mode is not enabled.",
            },
        )
    try:
        return await get_bundle(instrument, symbol, range_key, interval)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REQUEST", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "PROVIDER_FAILURE", "message": str(exc)},
        ) from exc


@app.get("/")
async def root() -> dict:
    return {
        "service": "qrdesk-cloud-market-gateway",
        "version": "0.7.1",
        "health": "/v1/market/health",
        "docs": "/docs",
    }
