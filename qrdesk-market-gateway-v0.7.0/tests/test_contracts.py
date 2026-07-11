from datetime import datetime, timezone

from qrdesk_gateway.contracts import date_window, filter_range_bars, meta_for, parse_market_time


def test_known_instruments_are_mapped():
    assert meta_for("US.AAPL").currency == "USD"
    assert meta_for("HK.00700").timezone == "Asia/Hong_Kong"
    assert meta_for("SH.600519").exchange == "SSE"


def test_date_window_selected_date_is_exact():
    assert date_window("1d", "2026-07-10") == ("2026-07-10", "2026-07-10")


def test_market_time_is_epoch_milliseconds():
    value = parse_market_time("2026-07-10 09:30:00", "America/New_York")
    assert value > 1_000_000_000_000


def test_one_day_filter_keeps_last_market_date():
    a = parse_market_time("2026-07-09 15:55:00", "America/New_York")
    b = parse_market_time("2026-07-10 09:30:00", "America/New_York")
    c = parse_market_time("2026-07-10 09:35:00", "America/New_York")
    bars = [
        {"time": a, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
        {"time": b, "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2},
        {"time": c, "open": 3, "high": 3, "low": 3, "close": 3, "volume": 3},
    ]
    assert [item["close"] for item in filter_range_bars(bars, "1d", "America/New_York")] == [2, 3]


def test_numeric_epoch_seconds_are_promoted_to_ms():
    seconds = int(datetime(2026, 7, 10, tzinfo=timezone.utc).timestamp())
    assert parse_market_time(seconds, "UTC") == seconds * 1000
