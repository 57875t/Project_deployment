from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

INSTRUMENTS = {
    "US.AAPL": ("AAPL", "US", "NASDAQ", "USD", "America/New_York"),
    "US.MSFT": ("MSFT", "US", "NASDAQ", "USD", "America/New_York"),
    "US.NVDA": ("NVDA", "US", "NASDAQ", "USD", "America/New_York"),
    "US.TSLA": ("TSLA", "US", "NASDAQ", "USD", "America/New_York"),
    "US.AMZN": ("AMZN", "US", "NASDAQ", "USD", "America/New_York"),
    "US.GOOGL": ("GOOGL", "US", "NASDAQ", "USD", "America/New_York"),
    "US.META": ("META", "US", "NASDAQ", "USD", "America/New_York"),
    "US.SPY": ("SPY", "US", "NYSEARCA", "USD", "America/New_York"),
    "US.QQQ": ("QQQ", "US", "NASDAQ", "USD", "America/New_York"),
    "HK.00700": ("0700.HK", "HK", "HKEX", "HKD", "Asia/Hong_Kong"),
    "HK.09988": ("9988.HK", "HK", "HKEX", "HKD", "Asia/Hong_Kong"),
    "HK.03690": ("3690.HK", "HK", "HKEX", "HKD", "Asia/Hong_Kong"),
    "SH.600519": ("600519.SH", "CN", "SSE", "CNY", "Asia/Shanghai"),
    "SZ.000001": ("000001.SZ", "CN", "SZSE", "CNY", "Asia/Shanghai"),
    "SZ.300750": ("300750.SZ", "CN", "SZSE", "CNY", "Asia/Shanghai"),
}

RANGES = {
    "1d": ("5m", 5, "minute", 3),
    "5d": ("15m", 15, "minute", 10),
    "1mo": ("1h", 1, "hour", 45),
    "6mo": ("1d", 1, "day", 220),
}


def _ms(value: Any) -> int:
    n = float(value)
    return int(n if n > 10_000_000_000 else n * 1000)


def _validate(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    last = -1
    now = int(time.time() * 1000) + 300_000
    for bar in bars:
        try:
            item = {
                "time": _ms(bar["time"]),
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": float(bar.get("volume") or 0),
            }
        except (KeyError, TypeError, ValueError):
            continue
        if item["time"] <= last or item["time"] > now:
            continue
        if item["high"] < max(item["open"], item["close"]) or item["low"] > min(item["open"], item["close"]):
            continue
        if item["low"] < 0 or item["volume"] < 0:
            continue
        clean.append(item)
        last = item["time"]
    if not clean:
        raise RuntimeError("provider returned no valid OHLCV bars")
    return clean


async def _massive(instrument: str, range_key: str) -> tuple[list[dict[str, Any]], str, list[str]]:
    key = os.getenv("MASSIVE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MASSIVE_API_KEY is not configured")
    symbol, *_ = INSTRUMENTS[instrument]
    interval, multiplier, timespan, lookback = RANGES[range_key]
    end = datetime.now(timezone.utc).date()
    start = end.fromordinal(end.toordinal() - lookback)
    url = f"https://api.massive.com/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start}/{end}"
    async with httpx.AsyncClient(timeout=float(os.getenv("QRDESK_PROVIDER_TIMEOUT_SECONDS", "12"))) as client:
        response = await client.get(url, params={"adjusted": "true", "sort": "asc", "limit": 5000, "apiKey": key})
        response.raise_for_status()
        payload = response.json()
    rows = payload.get("results") or []
    bars = [{"time": r.get("t"), "open": r.get("o"), "high": r.get("h"), "low": r.get("l"), "close": r.get("c"), "volume": r.get("v")} for r in rows]
    recency = os.getenv("MASSIVE_RECENCY", "plan-dependent")
    return _validate(bars), recency, []


async def _eodhd(instrument: str, range_key: str) -> tuple[list[dict[str, Any]], str, list[str]]:
    token = os.getenv("EODHD_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("EODHD_API_TOKEN is not configured")
    symbol, *_ = INSTRUMENTS[instrument]
    interval = RANGES[range_key][0]
    provider_interval = {"5m": "5m", "15m": "5m", "1h": "1h", "1d": "d"}[interval]
    url = f"https://eodhd.com/api/intraday/{symbol}"
    async with httpx.AsyncClient(timeout=float(os.getenv("QRDESK_PROVIDER_TIMEOUT_SECONDS", "12"))) as client:
        response = await client.get(url, params={"api_token": token, "fmt": "json", "interval": provider_interval})
        response.raise_for_status()
        rows = response.json()
    bars = [{"time": r.get("timestamp") or r.get("datetime"), "open": r.get("open"), "high": r.get("high"), "low": r.get("low"), "close": r.get("close"), "volume": r.get("volume")} for r in rows]
    warnings = ["EODHD data is labeled delayed/historical and is not represented as exchange-direct real-time."]
    return _validate(bars), os.getenv("EODHD_RECENCY", "delayed-historical"), warnings


async def get_bundle(instrument: str, symbol: str, range_key: str, interval: str) -> dict[str, Any]:
    if instrument not in INSTRUMENTS:
        raise ValueError("unsupported instrument")
    if range_key not in RANGES or interval != RANGES[range_key][0]:
        raise ValueError("range/interval mismatch")
    meta_symbol, market, exchange, currency, timezone_name = INSTRUMENTS[instrument]
    attempts: list[dict[str, Any]] = []
    providers = [(_massive, "Massive")] if market == "US" else []
    providers.append((_eodhd, "EODHD"))
    for provider, name in providers:
        try:
            bars, recency, warnings = await provider(instrument, range_key)
            last = bars[-1]
            return {
                "ok": True,
                "instrument": {"code": instrument, "symbol": symbol or meta_symbol, "market": market, "exchange": exchange, "currency": currency, "timezone": timezone_name, "assetType": "EQUITY"},
                "quote": {"lastPrice": last["close"], "open": last["open"], "high": last["high"], "low": last["low"], "volume": last["volume"], "previousClose": bars[-2]["close"] if len(bars) > 1 else None, "session": "unknown", "updateTime": datetime.fromtimestamp(last["time"] / 1000, tz=timezone.utc).isoformat()},
                "fundamentals": {},
                "bars": bars,
                "provenance": {"provider": name, "entitlement": "configured", "recency": recency, "asOf": datetime.fromtimestamp(last["time"] / 1000, tz=timezone.utc).isoformat(), "fetchedAt": datetime.now(timezone.utc).isoformat(), "adjustment": "provider-default", "barTimestampConvention": "start", "delaySeconds": max(0, time.time() - last["time"] / 1000), "requestId": uuid.uuid4().hex, "warnings": warnings, "attempts": attempts},
            }
        except Exception as exc:
            attempts.append({"provider": name, "ok": False, "error": str(exc)})
    raise RuntimeError(f"all configured providers failed: {attempts}")
