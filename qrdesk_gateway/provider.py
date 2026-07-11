from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .kline_engine import (
    aggregate_bars_strict,
    audit_bars,
    normalize_bars,
)
from .session_engine import calibrate_session_bars


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


def _merge_counters(*groups: dict[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for group in groups:
        for key, value in group.items():
            merged[key] = merged.get(key, 0) + int(value)
    return merged


def _actual_previous_close(
    bars: list[dict[str, Any]],
    *,
    timezone_name: str,
    interval: str,
) -> float | None:
    if len(bars) < 2:
        return None
    if interval == "1d":
        return float(bars[-2]["close"])

    timezone_info = ZoneInfo(timezone_name)
    latest_date = datetime.fromtimestamp(
        int(bars[-1]["time"]) / 1000,
        tz=timezone.utc,
    ).astimezone(timezone_info).date()
    for bar in reversed(bars[:-1]):
        bar_date = datetime.fromtimestamp(
            int(bar["time"]) / 1000,
            tz=timezone.utc,
        ).astimezone(timezone_info).date()
        if bar_date < latest_date:
            return float(bar["close"])
    return None


def _append_quality_warnings(
    warnings: list[str],
    counters: dict[str, int],
) -> list[str]:
    result = list(warnings)
    messages = {
        "offSessionCount": "Off-session provider bars were removed.",
        "incompleteCount": "Still-forming bars were removed.",
        "partialAggregationCount": "Incomplete aggregate buckets were removed.",
        "invalidCount": "Invalid OHLCV records were removed.",
        "futureCount": "Future-dated records were removed.",
        "duplicateCount": "Duplicate timestamps were reconciled by keeping the last provider record.",
    }
    for key, message in messages.items():
        if counters.get(key, 0):
            result.append(f"{message} count={counters[key]}")
    return result


async def _massive(
    instrument: str,
    range_key: str,
) -> tuple[list[dict[str, Any]], str, list[str], dict[str, int], dict[str, Any]]:
    key = os.getenv("MASSIVE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MASSIVE_API_KEY is not configured")

    symbol, market, _, _, timezone_name = INSTRUMENTS[instrument]
    interval, multiplier, timespan, lookback = RANGES[range_key]
    end = datetime.now(timezone.utc).date()
    start = end.fromordinal(end.toordinal() - lookback)
    url = (
        f"https://api.massive.com/v2/aggs/ticker/{symbol}/range/"
        f"{multiplier}/{timespan}/{start}/{end}"
    )
    async with httpx.AsyncClient(
        timeout=float(os.getenv("QRDESK_PROVIDER_TIMEOUT_SECONDS", "12"))
    ) as client:
        response = await client.get(
            url,
            params={
                "adjusted": "true",
                "sort": "asc",
                "limit": 5000,
                "apiKey": key,
            },
        )
        response.raise_for_status()
        payload = response.json()

    rows = payload.get("results") or []
    raw = [
        {
            "time": row.get("t"),
            "open": row.get("o"),
            "high": row.get("h"),
            "low": row.get("l"),
            "close": row.get("c"),
            "volume": row.get("v"),
        }
        for row in rows
    ]
    bars, normalize_counters = normalize_bars(
        raw,
        timezone_name=timezone_name,
    )
    bars, session_counters, snapshot = calibrate_session_bars(
        bars,
        market=market,
        interval_seconds=INTERVAL_SECONDS[interval],
    )
    counters = _merge_counters(normalize_counters, session_counters)
    if not bars:
        raise RuntimeError("Massive returned no complete regular-session OHLCV bars")

    return (
        bars,
        os.getenv("MASSIVE_RECENCY", "plan-dependent"),
        [],
        counters,
        snapshot.to_dict(),
    )


async def _eodhd(
    instrument: str,
    range_key: str,
) -> tuple[list[dict[str, Any]], str, list[str], dict[str, int], dict[str, Any]]:
    token = os.getenv("EODHD_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("EODHD_API_TOKEN is not configured")

    symbol, market, _, _, timezone_name = INSTRUMENTS[instrument]
    interval = RANGES[range_key][0]
    provider_interval = {
        "5m": "5m",
        "15m": "5m",
        "1h": "1h",
        "1d": "d",
    }[interval]
    endpoint = "eod" if interval == "1d" else "intraday"
    url = f"https://eodhd.com/api/{endpoint}/{symbol}"
    params: dict[str, Any] = {"api_token": token, "fmt": "json"}
    if endpoint == "intraday":
        params["interval"] = provider_interval

    async with httpx.AsyncClient(
        timeout=float(os.getenv("QRDESK_PROVIDER_TIMEOUT_SECONDS", "12"))
    ) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        rows = response.json()

    raw = [
        {
            "time": row.get("timestamp") or row.get("datetime") or row.get("date"),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "volume": row.get("volume"),
        }
        for row in rows
    ]
    bars, normalize_counters = normalize_bars(
        raw,
        timezone_name=timezone_name,
    )

    source_interval_seconds = 300 if interval == "15m" else INTERVAL_SECONDS[interval]
    bars, session_counters, snapshot = calibrate_session_bars(
        bars,
        market=market,
        interval_seconds=source_interval_seconds,
    )
    partial_aggregation_count = 0
    if interval == "15m":
        bars, partial_aggregation_count = aggregate_bars_strict(
            bars,
            source_seconds=300,
            target_seconds=900,
        )

    counters = _merge_counters(
        normalize_counters,
        session_counters,
        {"partialAggregationCount": partial_aggregation_count},
    )
    if not bars:
        raise RuntimeError("EODHD returned no complete regular-session OHLCV bars")

    warnings = [
        "EODHD data is delayed/historical and is not represented as exchange-direct real-time."
    ]
    return (
        bars,
        os.getenv("EODHD_RECENCY", "delayed-historical"),
        warnings,
        counters,
        snapshot.to_dict(),
    )


async def get_bundle(
    instrument: str,
    symbol: str,
    range_key: str,
    interval: str,
) -> dict[str, Any]:
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
            bars, recency, warnings, counters, market_session = await provider(
                instrument,
                range_key,
            )
            quality = audit_bars(
                bars,
                expected_interval_seconds=INTERVAL_SECONDS[interval],
                counters=counters,
                market=market,
            )
            last = bars[-1]
            update_time = datetime.fromtimestamp(
                int(last["time"]) / 1000,
                tz=timezone.utc,
            ).isoformat()
            previous_close = _actual_previous_close(
                bars,
                timezone_name=timezone_name,
                interval=interval,
            )
            last_price = float(last["close"])
            change = None if previous_close is None else last_price - previous_close
            change_percent = (
                None
                if previous_close in (None, 0)
                else change / previous_close * 100
            )
            warnings = _append_quality_warnings(warnings, counters)

            return {
                "ok": True,
                "instrument": {
                    "code": instrument,
                    "symbol": symbol or meta_symbol,
                    "market": market,
                    "exchange": exchange,
                    "currency": currency,
                    "timezone": timezone_name,
                    "assetType": "EQUITY",
                },
                "quote": {
                    "lastPrice": last_price,
                    "open": last["open"],
                    "high": last["high"],
                    "low": last["low"],
                    "volume": last["volume"],
                    "previousClose": previous_close,
                    "change": change,
                    "changePercent": change_percent,
                    "barChange": quality.change_amount,
                    "barChangePercent": quality.change_percent,
                    "session": market_session["state"],
                    "updateTime": update_time,
                    "priceSemantics": "last-completed-bar-close",
                    "isIndependentQuote": False,
                },
                "marketSession": market_session,
                "fundamentals": {},
                "bars": bars,
                "quality": {
                    "verdict": quality.verdict,
                    "barCount": quality.bar_count,
                    "duplicateCount": quality.duplicate_count,
                    "invalidCount": quality.invalid_count,
                    "gapCount": quality.gap_count,
                    "futureCount": quality.future_count,
                    "offSessionCount": quality.off_session_count,
                    "incompleteCount": quality.incomplete_count,
                    "truncatedSegmentCount": quality.truncated_segment_count,
                    "partialAggregationCount": quality.partial_aggregation_count,
                    "freshnessSeconds": quality.freshness_seconds,
                },
                "provenance": {
                    "provider": name,
                    "entitlement": "configured",
                    "recency": recency,
                    "asOf": update_time,
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                    "adjustment": (
                        "provider-adjusted"
                        if name == "Massive"
                        else "provider-default"
                    ),
                    "barTimestampConvention": "provider-start-assumed",
                    "quoteSemantics": "last-completed-bar-close",
                    "calendar": market_session["calendar"],
                    "delaySeconds": max(
                        0,
                        time.time() - int(last["time"]) / 1000,
                    ),
                    "requestId": uuid.uuid4().hex,
                    "warnings": warnings,
                    "attempts": attempts,
                    "syntheticBars": 0,
                },
            }
        except Exception as exc:
            attempts.append(
                {
                    "provider": name,
                    "ok": False,
                    "error": str(exc),
                }
            )

    raise RuntimeError(f"all configured providers failed: {attempts}")
