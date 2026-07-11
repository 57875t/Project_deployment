from datetime import datetime

from qrdesk_gateway.session_engine import (
    calibrate_session_bars,
    session_gap_count,
    session_snapshot,
)


def _ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def _bar(time: str, close: float = 10.0) -> dict:
    return {
        "time": _ms(time),
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 100.0,
    }


def test_weekend_reports_closed_non_session():
    snapshot = session_snapshot(
        "US",
        now_ms=_ms("2026-07-11T15:00:00Z"),
    )
    assert snapshot.state == "closed_non_session"
    assert snapshot.is_trading_day is False
    assert snapshot.calendar == "XNYS"


def test_incomplete_and_off_session_intraday_bars_are_removed():
    bars = [
        _bar("2026-07-10T13:25:00Z"),
        _bar("2026-07-10T13:30:00Z"),
        _bar("2026-07-10T13:35:00Z"),
    ]
    kept, counters, snapshot = calibrate_session_bars(
        bars,
        market="US",
        interval_seconds=300,
        now_ms=_ms("2026-07-10T13:37:00Z"),
    )
    assert [bar["time"] for bar in kept] == [_ms("2026-07-10T13:30:00Z")]
    assert counters["offSessionCount"] == 1
    assert counters["incompleteCount"] == 1
    assert snapshot.state == "open"


def test_hong_kong_lunch_break_is_not_counted_as_data_gap():
    bars = [
        _bar("2026-07-10T03:55:00Z"),
        _bar("2026-07-10T05:00:00Z"),
    ]
    assert session_gap_count(
        bars,
        market="HK",
        interval_seconds=300,
    ) == 0


def test_current_daily_bar_is_removed_until_session_closes():
    bar = _bar("2026-07-09T16:00:00Z")
    kept, counters, snapshot = calibrate_session_bars(
        [bar],
        market="CN",
        interval_seconds=86_400,
        now_ms=_ms("2026-07-10T06:00:00Z"),
    )
    assert kept == []
    assert counters["incompleteCount"] == 1
    assert snapshot.state == "open"

    kept_after_close, counters_after_close, snapshot_after_close = calibrate_session_bars(
        [bar],
        market="CN",
        interval_seconds=86_400,
        now_ms=_ms("2026-07-10T08:00:00Z"),
    )
    assert kept_after_close == [bar]
    assert counters_after_close["incompleteCount"] == 0
    assert snapshot_after_close.state == "post_close"
