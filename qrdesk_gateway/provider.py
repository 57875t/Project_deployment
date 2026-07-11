from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from .kline_engine import aggregate_bars, audit_bars, normalize_bars

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

INTERVAL_SECONDS = {"5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


async def _massive(instrument: str, range_key: str) -> tuple[list[dict[str, Any]], str, list[str], dict[str, int]]:
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
    raw = [{"time": r.get("t"), "open": r.get("o"), "high": r.get("h"), "low": r.get("l"), "close": r.get("c"), "volume": r.get("v")} for r in rows]
    bars, counters = normalize_bars(raw)
    if not bars:
        raise RuntimeError("Massive returned no valid OHLCV bars")
    return bars, os.getenv("MASSIVE_RECENCY", "plan-dependent"), [], counters


async def _eodhd(instrument: str, range_key: str) -> tuple[list[dict[str, Any]], str, list[str], dict[str, int]]:
    token = os.getenv("EODHD_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("EODHD_API_TOKEN is not configured")
    symbol, *_ = INSTRUMENTS[instrument]
    interval = RANGES[range_key][0]
    provider_interval = {"5m": "5m", "15m": "5m", "1h": "1h", "1d": "d"}[interval]
    endpoint = "eod" if interval == "1d" else "intraday"
    url = f"https://eodhd.com/api/{endpoint}/{symbol}"
    params: dict[str, Any] = {"api_token": token, "fmt": "json"}
    if endpoint == "intraday":
        params["interval"] = provider_interval
    async with httpx.AsyncClient(timeout=float(os.getenv("QRDESK_PROVIDER_TIMEOUT_SECONDS", "12"))) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        rows = response.json()
    raw = [{"time": r.get("timestamp") or r.get("datetime") or r.get("date"), "open": r.get("open"), "high": r.get("high"), "low": r.get("low"), "close": r.get("close"), "volume": r.get("volume")} for r in rows]
    bars, counters = normalize_bars(raw)
    if interval == "15m":
        bars = aggregate_bars(bars, target_seconds=900)
    if not bars:
        raise RuntimeError("EODHD returned no valid OHLCV bars")
    warnings = ["EODHD data is delayed/historical and is not represented as exchange-direct real-time."]
    return bars, os.getenv("EODHD_RECENCY", "delayed-historical"), warnings, counters


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
            bars, recency, warnings, counters = await provider(instrument, range_key)
            quality = audit_bars(bars, expected_interval_seconds=INTERVAL_SECONDS[interval], counters=counters)
            last = bars[-1]
            update_time = datetime.fromtimestamp(int(last["time"]) / 1000, tz=timezone.utc).isoformat()
            return {
                "ok": True,
                "instrument": {"code": instrument, "symbol": symbol or meta_symbol, "market": market, "exchange": exchange, "currency": currency, "timezone": timezone_name, "assetType": "EQUITY"},
                "quote": {
                    "lastPrice": last["close"],
                    "open": last["open"],
                    "high": last["high"],
                    "low": last["low"],
                    "volume": last["volume"],
                    "previousClose": bars[-2]["close"] if len(bars) > 1 else None,
                    "change": quality.change_amount,
                    "changePercent": quality.change_percent,
                    "session": "provider-derived",
                    "updateTime": update_time,
                },
                "fundamentals": {},
                "bars": bars,
                "quality": {
                    "verdict": quality.verdict,
                    "barCount": quality.bar_count,
                    "duplicateCount": quality.duplicate_count,
                    "invalidCount": quality.invalid_count,
                    "gapCount": quality.gap_count,
                    "futureCount": quality.future_count,
                    "freshnessSeconds": quality.freshness_seconds,
                },
                "provenance": {
                    "provider": name,
                    "entitlement": "configured",
                    "recency": recency,
                    "asOf": update_time,
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                    "adjustment": "provider-adjusted" if name == "Massive" else "provider-default",
                    "barTimestampConvention": "start",
                    "delaySeconds": max(0, time.time() - int(last["time"]) / 1000),
                    "requestId": uuid.uuid4().hex,
                    "warnings": warnings,
                    "attempts": attempts,
                    "syntheticBars": 0,
                },
            }
        except Exception as exc:
            attempts.append({"provider": name, "ok": False, "error": str(exc)})
    raise RuntimeError(f"all configured providers failed: {attempts}")
