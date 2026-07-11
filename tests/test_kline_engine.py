from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from qrdesk_gateway.kline_engine import (
    aggregate_bars,
    aggregate_bars_strict,
    audit_bars,
    normalize_bars,
)


def _ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def test_normalize_rejects_invalid_and_future_bars():
    now_ms = 1_700_000_000_000
    bars, counters = normalize_bars(
        [
            {"time": now_ms - 600_000, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100},
            {"time": now_ms - 600_000, "open": 10, "high": 13, "low": 9, "close": 12, "volume": 110},
            {"time": now_ms - 300_000, "open": 10, "high": 9, "low": 8, "close": 10, "volume": 100},
            {"time": now_ms + 120_000, "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
        ],
        now_ms=now_ms,
    )
    assert len(bars) == 1
    assert bars[0]["close"] == 12
    assert counters == {"duplicateCount": 1, "invalidCount": 1, "futureCount": 1}


def test_normalize_parses_exchange_local_iso_date():
    bars, counters = normalize_bars(
        [
            {
                "time": "2026-07-10",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10,
                "volume": 100,
            }
        ],
        timezone_name="Asia/Shanghai",
        now_ms=_ms("2026-07-11T00:00:00Z"),
    )
    local = datetime.fromtimestamp(
        bars[0]["time"] / 1000,
        tz=timezone.utc,
    ).astimezone(ZoneInfo("Asia/Shanghai"))
    assert local.date().isoformat() == "2026-07-10"
    assert counters == {"duplicateCount": 0, "invalidCount": 0, "futureCount": 0}


def test_aggregate_5m_to_15m_is_deterministic():
    bars = [
        {"time": 0, "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 100.0},
        {"time": 300_000, "open": 11.0, "high": 13.0, "low": 10.0, "close": 12.0, "volume": 200.0},
        {"time": 600_000, "open": 12.0, "high": 14.0, "low": 11.0, "close": 13.0, "volume": 300.0},
    ]
    result = aggregate_bars(bars, target_seconds=900)
    assert result == [{"time": 0, "open": 10.0, "high": 14.0, "low": 9.0, "close": 13.0, "volume": 600.0}]


def test_strict_aggregation_drops_partial_bucket():
    bars = [
        {"time": 0, "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 100.0},
        {"time": 300_000, "open": 11.0, "high": 13.0, "low": 10.0, "close": 12.0, "volume": 200.0},
    ]
    result, partial_count = aggregate_bars_strict(
        bars,
        source_seconds=300,
        target_seconds=900,
    )
    assert result == []
    assert partial_count == 1


def test_audit_calculates_change_and_gaps():
    bars = [
        {"time": 0, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "volume": 100.0},
        {"time": 900_000, "open": 10.0, "high": 12.0, "low": 10.0, "close": 12.0, "volume": 100.0},
    ]
    quality = audit_bars(bars, expected_interval_seconds=300, now_ms=900_000)
    assert quality.gap_count == 2
    assert quality.change_amount == 2.0
    assert quality.change_percent == 20.0
    assert quality.verdict == "WARN"
