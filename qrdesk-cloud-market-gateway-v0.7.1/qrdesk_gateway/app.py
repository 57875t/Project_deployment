from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .provider import INSTRUMENTS, RANGES, get_bundle

app = FastAPI(title="QR Desk Cloud Market Gateway", version="0.7.1")
origins = [item.strip() for item in os.getenv("QRDESK_ALLOWED_ORIGINS", "*").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/v1/market/health")
async def health() -> dict:
    providers = {
        "massive": bool(os.getenv("MASSIVE_API_KEY", "").strip()),
        "eodhd": bool(os.getenv("EODHD_API_TOKEN", "").strip()),
    }
    configured = [name for name, value in providers.items() if value]
    return {
        "ok": bool(configured),
        "status": "ok" if configured else "degraded",
        "provider": ", ".join(configured) if configured else "none",
        "entitlement": "configured" if configured else "missing",
        "openD": "not_required",
        "message": "Cloud market-data provider configured." if configured else "No cloud provider API key is configured.",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "instruments": len(INSTRUMENTS),
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
        raise HTTPException(status_code=501, detail={"code": "HISTORICAL_DATE_NOT_IMPLEMENTED", "message": "Exact historical-date mode is not yet enabled in the cloud gateway."})
    if extended:
        raise HTTPException(status_code=400, detail={"code": "EXTENDED_UNSUPPORTED", "message": "Extended-hours mode is not enabled."})
    try:
        return await get_bundle(instrument, symbol, range_key, interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "PROVIDER_FAILURE", "message": str(exc)}) from exc


@app.get("/")
async def root() -> dict:
    return {"service": "qrdesk-cloud-market-gateway", "version": "0.7.1", "docs": "/docs"}
