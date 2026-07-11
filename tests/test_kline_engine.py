from qrdesk_gateway.kline_engine import aggregate_bars, audit_bars, normalize_bars


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


def test_aggregate_5m_to_15m_is_deterministic():
    bars = [
        {"time": 0, "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 100.0},
        {"time": 300_000, "open": 11.0, "high": 13.0, "low": 10.0, "close": 12.0, "volume": 200.0},
        {"time": 600_000, "open": 12.0, "high": 14.0, "low": 11.0, "close": 13.0, "volume": 300.0},
    ]
    result = aggregate_bars(bars, target_seconds=900)
    assert result == [{"time": 0, "open": 10.0, "high": 14.0, "low": 9.0, "close": 13.0, "volume": 600.0}]


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
