from __future__ import annotations

import math
import threading
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from .config import settings
from .contracts import INTERVAL_SECONDS, RANGE_CONFIG, date_window, filter_range_bars, meta_for, parse_market_time
from .errors import GatewayError

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    import moomoo as ft
except Exception:  # pragma: no cover
    ft = None


def _finite(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _pick(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            value = record[name]
            if value is not None and not (isinstance(value, float) and math.isnan(value)):
                return value
    return None


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    if isinstance(frame, list):
        return [item for item in frame if isinstance(item, dict)]
    return []


class MoomooProvider:
    """Read-only wrapper around one Moomoo OpenQuoteContext.

    It never creates a trade context, never asks for a trading password, and
    never sends an order.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ctx: Any = None

    def _require_sdk(self) -> None:
        if ft is None:
            raise GatewayError(
                "SDK_NOT_INSTALLED",
                "Python package 'moomoo-api' is not installed. Run: pip install -r requirements.txt",
                status_code=503,
            )

    def _ensure_context(self) -> Any:
        self._require_sdk()
        if self._ctx is None:
            try:
                self._ctx = ft.OpenQuoteContext(
                    host=settings.opend_host,
                    port=settings.opend_port,
                    is_async_connect=True,
                )
                if hasattr(self._ctx, "set_sync_query_connect_timeout"):
                    self._ctx.set_sync_query_connect_timeout(settings.query_connect_timeout)
            except Exception as exc:
                self._ctx = None
                raise GatewayError(
                    "OPEND_CONNECT_FAILED",
                    f"Cannot create OpenQuoteContext at {settings.opend_host}:{settings.opend_port}: {exc}",
                    status_code=503,
                ) from exc
        return self._ctx

    def close(self) -> None:
        with self._lock:
            if self._ctx is not None:
                with suppress(Exception):
                    self._ctx.close()
                self._ctx = None

    def _check(self, result: tuple, operation: str) -> Any:
        if not isinstance(result, tuple) or len(result) < 2:
            raise GatewayError("SDK_RESPONSE_INVALID", f"{operation} returned an unexpected value", status_code=502)
        ret, data = result[0], result[1]
        if ret != ft.RET_OK:
            raise GatewayError("OPEND_QUERY_FAILED", f"{operation} failed: {data}", status_code=502)
        return data

    def health(self) -> dict[str, Any]:
        with self._lock:
            ctx = self._ensure_context()
            state = self._check(ctx.get_global_state(), "get_global_state")
            state = state if isinstance(state, dict) else {}
            qot_logined = str(state.get("qot_logined", "0")) == "1"
            return {
                "ok": qot_logined,
                "status": "ok" if qot_logined else "degraded",
                "provider": "moomoo OpenD",
                "entitlement": "verified-per-request",
                "openD": _text(state.get("server_ver")) or "connected",
                "message": "OpenD quote service is connected." if qot_logined else "OpenD is reachable, but quote service is not logged in.",
                "state": {
                    "qotLogined": qot_logined,
                    "marketUS": _text(state.get("market_us")),
                    "marketHK": _text(state.get("market_hk")),
                    "marketSH": _text(state.get("market_sh")),
                    "marketSZ": _text(state.get("market_sz")),
                },
            }

    def _kline_type(self, interval: str) -> Any:
        mapping = {"5m": "K_5M", "15m": "K_15M", "1h": "K_60M", "1d": "K_DAY"}
        attr = mapping.get(interval)
        if not attr or not hasattr(ft.KLType, attr):
            raise GatewayError("INTERVAL_UNSUPPORTED", f"Unsupported interval: {interval}", status_code=400)
        return getattr(ft.KLType, attr)

    def _fetch_history(self, ctx: Any, code: str, range_key: str, selected_date: str | None, extended: bool) -> list[dict[str, Any]]:
        cfg = RANGE_CONFIG[range_key]
        interval = str(cfg["interval"])
        start, end = date_window(range_key, selected_date)
        page_key = None
        frames: list[Any] = []

        for _ in range(settings.history_max_pages):
            result = ctx.request_history_kline(
                code,
                start=start,
                end=end,
                ktype=self._kline_type(interval),
                autype=ft.AuType.QFQ,
                max_count=1000,
                page_req_key=page_key,
                extended_time=bool(extended),
            )
            if not isinstance(result, tuple) or len(result) < 3:
                raise GatewayError("SDK_RESPONSE_INVALID", "request_history_kline returned an unexpected value", status_code=502)
            ret, data, page_key = result[0], result[1], result[2]
            if ret != ft.RET_OK:
                raise GatewayError("HISTORY_QUERY_FAILED", f"request_history_kline failed: {data}", status_code=502)
            frames.append(data)
            if page_key is None:
                break
        else:
            raise GatewayError("HISTORY_PAGE_LIMIT", "History pagination exceeded safety limit", status_code=502)

        if pd is not None and frames:
            records = _records(pd.concat(frames, ignore_index=True))
        else:
            records = [item for frame in frames for item in _records(frame)]

        meta = meta_for(code)
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        interval_ms = INTERVAL_SECONDS[interval] * 1000
        bars: list[dict[str, Any]] = []

        for row in records:
            try:
                timestamp = parse_market_time(_pick(row, "time_key", "time", "datetime"), meta.timezone)
            except Exception:
                continue
            # Treat OpenD timestamps as bar-start times and exclude a currently
            # forming intraday bar. The snapshot endpoint still carries live price.
            if interval != "1d" and timestamp + interval_ms > now_ms:
                continue
            bar = {
                "time": timestamp,
                "open": _finite(_pick(row, "open", "open_price")),
                "high": _finite(_pick(row, "high", "high_price")),
                "low": _finite(_pick(row, "low", "low_price")),
                "close": _finite(_pick(row, "close", "close_price")),
                "volume": _finite(_pick(row, "volume")),
            }
            if all(bar[key] is not None for key in ("open", "high", "low", "close", "volume")):
                bars.append(bar)
        return filter_range_bars(bars, range_key, meta.timezone)

    def _snapshot(self, ctx: Any, code: str) -> dict[str, Any]:
        data = self._check(ctx.get_market_snapshot([code]), "get_market_snapshot")
        rows = _records(data)
        if not rows:
            raise GatewayError("SNAPSHOT_EMPTY", f"No snapshot returned for {code}", status_code=502)
        return rows[0]

    @staticmethod
    def _market_state(state: dict[str, Any], code: str) -> str | None:
        prefix = code.split(".", 1)[0].upper()
        key = {"US": "market_us", "HK": "market_hk", "SH": "market_sh", "SZ": "market_sz"}.get(prefix)
        return _text(state.get(key)) if key else None

    def bundle(self, *, instrument: str, symbol: str, range_key: str, interval: str, selected_date: str | None, extended: bool) -> dict[str, Any]:
        if range_key not in RANGE_CONFIG:
            raise GatewayError("RANGE_UNSUPPORTED", f"Unsupported range: {range_key}", status_code=400)
        expected_interval = str(RANGE_CONFIG[range_key]["interval"])
        if interval != expected_interval:
            raise GatewayError("RANGE_INTERVAL_MISMATCH", f"Range {range_key} requires interval {expected_interval}, got {interval}", status_code=400)

        try:
            meta = meta_for(instrument)
        except ValueError as exc:
            raise GatewayError("INSTRUMENT_UNSUPPORTED", str(exc), status_code=400) from exc

        request_id = uuid.uuid4().hex
        fetched_at = datetime.now(tz=timezone.utc)
        with self._lock:
            ctx = self._ensure_context()
            global_state = self._check(ctx.get_global_state(), "get_global_state")
            global_state = global_state if isinstance(global_state, dict) else {}
            bars = self._fetch_history(ctx, instrument, range_key, selected_date, extended)
            snapshot = self._snapshot(ctx, instrument)

        update_time_raw = _pick(snapshot, "update_time", "update_timestamp", "time")
        update_time_iso: str | None = None
        delay_seconds: float | None = None
        if update_time_raw:
            try:
                update_ms = parse_market_time(update_time_raw, meta.timezone)
                update_time_iso = datetime.fromtimestamp(update_ms / 1000, tz=timezone.utc).isoformat()
                delay_seconds = max(0.0, (fetched_at.timestamp() * 1000 - update_ms) / 1000)
            except Exception:
                update_time_iso = _text(update_time_raw)

        quote = {
            "lastPrice": _finite(_pick(snapshot, "last_price", "lastPrice")),
            "open": _finite(_pick(snapshot, "open_price", "open")),
            "high": _finite(_pick(snapshot, "high_price", "high")),
            "low": _finite(_pick(snapshot, "low_price", "low")),
            "volume": _finite(_pick(snapshot, "volume")),
            "previousClose": _finite(_pick(snapshot, "prev_close_price", "previous_close", "last_close")),
            "afterHoursPrice": _finite(_pick(snapshot, "after_hours_last_price", "after_hours_price")),
            "afterHoursChange": _finite(_pick(snapshot, "after_hours_change_val", "after_hours_change")),
            "afterHoursChangePercent": _finite(_pick(snapshot, "after_hours_change_rate", "after_hours_change_percent")),
            "session": self._market_state(global_state, instrument),
            "updateTime": update_time_iso,
        }
        fundamentals = {
            "peTtm": _finite(_pick(snapshot, "pe_ratio", "pe_ttm_ratio", "pe_ttm")),
            "marketCap": _finite(_pick(snapshot, "market_val", "market_cap")),
            "dividendYield": _finite(_pick(snapshot, "dividend_ratio_ttm", "dividend_yield")),
            "averageVolume": _finite(_pick(snapshot, "average_volume", "avg_volume")),
            "high52Week": _finite(_pick(snapshot, "high_price_52_week", "highest_52_weeks_price", "week_52_high")),
            "low52Week": _finite(_pick(snapshot, "low_price_52_week", "lowest_52_weeks_price", "week_52_low")),
            "beta": _finite(_pick(snapshot, "beta")),
            "eps": _finite(_pick(snapshot, "earnings_per_share", "eps")),
        }
        return {
            "ok": True,
            "instrument": {
                "code": instrument,
                "symbol": symbol,
                "market": meta.market,
                "exchange": meta.exchange,
                "currency": meta.currency,
                "timezone": meta.timezone,
                "assetType": meta.asset_type,
            },
            "quote": quote,
            "fundamentals": fundamentals,
            "bars": bars,
            "provenance": {
                "provider": "moomoo OpenD",
                "entitlement": "available" if bars and quote["lastPrice"] is not None else "partial",
                "asOf": update_time_iso or fetched_at.isoformat(),
                "fetchedAt": fetched_at.isoformat(),
                "adjustment": "forward",
                "barTimestampConvention": "date" if interval == "1d" else "start",
                "delaySeconds": delay_seconds,
                "requestId": request_id,
                "warnings": [] if bars else ["No K-line bars returned for the requested range/date."],
            },
        }


provider = MoomooProvider()
