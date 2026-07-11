from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable


@dataclass(frozen=True)
class KlineQuality:
    bar_count: int
    duplicate_count: int
    invalid_count: int
    gap_count: int
    future_count: int
    freshness_seconds: float | None
    change_amount: float | None
    change_percent: float | None
    verdict: str


def _as_float(value: Any) -> float:
    number = float(value)
    if not isfinite(number):
        raise ValueError("non-finite number")
    return number


def _as_ms(value: Any) -> int:
    number = float(value)
    return int(number if number > 10_000_000_000 else number * 1000)


def normalize_bars(raw_bars: Iterable[dict[str, Any]], *, now_ms: int | None = None) -> tuple[list[dict[str, float | int]], dict[str, int]]:
    """Normalize provider bars without inventing or interpolating prices.

    Duplicate timestamps keep the last provider record. Invalid and future bars are
    rejected. Missing intervals remain missing and are reported by the quality audit.
    """
    current_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    deduped: dict[int, dict[str, float | int]] = {}
    invalid_count = 0
    future_count = 0
    duplicate_count = 0

    for raw in raw_bars:
        try:
            timestamp = _as_ms(raw["time"])
            item = {
                "time": timestamp,
                "open": _as_float(raw["open"]),
                "high": _as_float(raw["high"]),
                "low": _as_float(raw["low"]),
                "close": _as_float(raw["close"]),
                "volume": max(0.0, _as_float(raw.get("volume", 0))),
            }
            if timestamp > current_ms + 60_000:
                future_count += 1
                continue
            if item["low"] < 0 or item["high"] < max(item["open"], item["close"]) or item["low"] > min(item["open"], item["close"]):
                invalid_count += 1
                continue
            if timestamp in deduped:
                duplicate_count += 1
            deduped[timestamp] = item
        except (KeyError, TypeError, ValueError, OverflowError):
            invalid_count += 1

    bars = [deduped[key] for key in sorted(deduped)]
    return bars, {
        "duplicateCount": duplicate_count,
        "invalidCount": invalid_count,
        "futureCount": future_count,
    }


def aggregate_bars(bars: list[dict[str, float | int]], *, target_seconds: int) -> list[dict[str, float | int]]:
    """Aggregate lower-frequency provider bars using exchange-time-aligned buckets.

    This is deterministic OHLCV aggregation, not simulation. Empty buckets are not
    filled because doing so would manufacture market observations.
    """
    if target_seconds <= 0:
        raise ValueError("target_seconds must be positive")
    bucket_ms = target_seconds * 1000
    buckets: dict[int, list[dict[str, float | int]]] = {}
    for bar in bars:
        bucket = int(bar["time"]) // bucket_ms * bucket_ms
        buckets.setdefault(bucket, []).append(bar)

    result: list[dict[str, float | int]] = []
    for bucket in sorted(buckets):
        rows = sorted(buckets[bucket], key=lambda item: int(item["time"]))
        result.append({
            "time": bucket,
            "open": float(rows[0]["open"]),
            "high": max(float(item["high"]) for item in rows),
            "low": min(float(item["low"]) for item in rows),
            "close": float(rows[-1]["close"]),
            "volume": sum(float(item["volume"]) for item in rows),
        })
    return result


def audit_bars(bars: list[dict[str, float | int]], *, expected_interval_seconds: int, now_ms: int | None = None, counters: dict[str, int] | None = None) -> KlineQuality:
    current_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    expected_ms = expected_interval_seconds * 1000
    gap_count = 0
    for previous, current in zip(bars, bars[1:]):
        delta = int(current["time"]) - int(previous["time"])
        if delta > expected_ms * 1.5:
            gap_count += max(1, round(delta / expected_ms) - 1)

    freshness = None
    change_amount = None
    change_percent = None
    if bars:
        freshness = max(0.0, (current_ms - int(bars[-1]["time"])) / 1000)
        if len(bars) > 1:
            previous_close = float(bars[-2]["close"])
            last_close = float(bars[-1]["close"])
            change_amount = last_close - previous_close
            change_percent = None if previous_close == 0 else change_amount / previous_close * 100

    counters = counters or {}
    verdict = "PASS"
    if not bars:
        verdict = "FAIL"
    elif counters.get("invalidCount", 0) or counters.get("futureCount", 0):
        verdict = "WARN"
    elif gap_count:
        verdict = "WARN"

    return KlineQuality(
        bar_count=len(bars),
        duplicate_count=counters.get("duplicateCount", 0),
        invalid_count=counters.get("invalidCount", 0),
        gap_count=gap_count,
        future_count=counters.get("futureCount", 0),
        freshness_seconds=freshness,
        change_amount=change_amount,
        change_percent=change_percent,
        verdict=verdict,
    )
