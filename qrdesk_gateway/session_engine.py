from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import exchange_calendars as xcals
import pandas as pd


CALENDAR_BY_MARKET = {
    "US": "XNYS",
    "HK": "XHKG",
    "CN": "XSHG",
}


@dataclass(frozen=True)
class SessionSnapshot:
    market: str
    calendar: str
    session_date: str
    state: str
    is_trading_day: bool
    open_ms: int | None
    break_start_ms: int | None
    break_end_ms: int | None
    close_ms: int | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {
            "market": data["market"],
            "calendar": data["calendar"],
            "sessionDate": data["session_date"],
            "state": data["state"],
            "isTradingDay": data["is_trading_day"],
            "openTime": data["open_ms"],
            "breakStart": data["break_start_ms"],
            "breakEnd": data["break_end_ms"],
            "closeTime": data["close_ms"],
        }


@lru_cache(maxsize=8)
def get_calendar(market: str):
    try:
        name = CALENDAR_BY_MARKET[market]
    except KeyError as exc:
        raise ValueError(f"unsupported market calendar: {market}") from exc
    return xcals.get_calendar(name)


def _utc_timestamp(ms: int) -> pd.Timestamp:
    return pd.Timestamp(ms, unit="ms", tz="UTC")


def _to_ms(value: pd.Timestamp | None) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value.timestamp() * 1000)


def _session_label_for_timestamp(calendar, timestamp: pd.Timestamp) -> str:
    return timestamp.tz_convert(calendar.tz).date().isoformat()


def _session_bounds(calendar, session_label: str) -> tuple[pd.Timestamp, pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp]:
    open_ts = calendar.session_open(session_label)
    close_ts = calendar.session_close(session_label)
    break_start = calendar.session_break_start(session_label)
    break_end = calendar.session_break_end(session_label)
    if pd.isna(break_start):
        break_start = None
    if pd.isna(break_end):
        break_end = None
    return open_ts, break_start, break_end, close_ts


def session_snapshot(market: str, *, now_ms: int | None = None) -> SessionSnapshot:
    current_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    now = _utc_timestamp(current_ms)
    calendar = get_calendar(market)
    session_label = _session_label_for_timestamp(calendar, now)

    if not calendar.is_session(session_label):
        return SessionSnapshot(
            market=market,
            calendar=calendar.name,
            session_date=session_label,
            state="closed_non_session",
            is_trading_day=False,
            open_ms=None,
            break_start_ms=None,
            break_end_ms=None,
            close_ms=None,
        )

    open_ts, break_start, break_end, close_ts = _session_bounds(calendar, session_label)
    if now < open_ts:
        state = "pre_open"
    elif break_start is not None and break_end is not None and break_start <= now < break_end:
        state = "break"
    elif now < close_ts:
        state = "open"
    else:
        state = "post_close"

    return SessionSnapshot(
        market=market,
        calendar=calendar.name,
        session_date=session_label,
        state=state,
        is_trading_day=True,
        open_ms=_to_ms(open_ts),
        break_start_ms=_to_ms(break_start),
        break_end_ms=_to_ms(break_end),
        close_ms=_to_ms(close_ts),
    )


def _intraday_segment(calendar, timestamp: pd.Timestamp) -> tuple[str, pd.Timestamp] | None:
    session_label = _session_label_for_timestamp(calendar, timestamp)
    if not calendar.is_session(session_label):
        return None

    open_ts, break_start, break_end, close_ts = _session_bounds(calendar, session_label)
    if break_start is None or break_end is None:
        if open_ts <= timestamp < close_ts:
            return "regular", close_ts
        return None

    if open_ts <= timestamp < break_start:
        return "morning", break_start
    if break_end <= timestamp < close_ts:
        return "afternoon", close_ts
    return None


def calibrate_session_bars(
    bars: list[dict[str, float | int]],
    *,
    market: str,
    interval_seconds: int,
    now_ms: int | None = None,
) -> tuple[list[dict[str, float | int]], dict[str, int], SessionSnapshot]:
    """Remove off-session and still-forming bars without filling missing prices."""

    current_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    current = _utc_timestamp(current_ms)
    calendar = get_calendar(market)
    snapshot = session_snapshot(market, now_ms=current_ms)

    kept: list[dict[str, float | int]] = []
    off_session_count = 0
    incomplete_count = 0
    truncated_segment_count = 0

    if interval_seconds >= 86_400:
        current_local_date = current.tz_convert(calendar.tz).date().isoformat()
        for bar in bars:
            timestamp = _utc_timestamp(int(bar["time"]))
            bar_session = _session_label_for_timestamp(calendar, timestamp)
            if not calendar.is_session(bar_session):
                off_session_count += 1
                continue
            if bar_session > current_local_date:
                off_session_count += 1
                continue
            if (
                bar_session == current_local_date
                and snapshot.is_trading_day
                and snapshot.state in {"pre_open", "open", "break"}
            ):
                incomplete_count += 1
                continue
            kept.append(bar)
    else:
        interval_ms = interval_seconds * 1000
        for bar in bars:
            start = _utc_timestamp(int(bar["time"]))
            segment = _intraday_segment(calendar, start)
            if segment is None:
                off_session_count += 1
                continue

            _, segment_end = segment
            nominal_end = start + pd.Timedelta(milliseconds=interval_ms)
            effective_end = min(nominal_end, segment_end)
            if nominal_end > segment_end:
                truncated_segment_count += 1
            if effective_end > current:
                incomplete_count += 1
                continue
            kept.append(bar)

    return kept, {
        "offSessionCount": off_session_count,
        "incompleteCount": incomplete_count,
        "truncatedSegmentCount": truncated_segment_count,
    }, snapshot


def session_gap_count(
    bars: list[dict[str, float | int]],
    *,
    market: str,
    interval_seconds: int,
) -> int:
    """Count gaps only inside valid trading segments.

    Overnight closures, weekends, holidays and lunch breaks are not reported as
    missing market observations.
    """

    if len(bars) < 2:
        return 0

    calendar = get_calendar(market)
    if interval_seconds >= 86_400:
        actual_dates = {
            _session_label_for_timestamp(calendar, _utc_timestamp(int(bar["time"])))
            for bar in bars
        }
        first = min(actual_dates)
        last = max(actual_dates)
        expected = {value.date().isoformat() for value in calendar.sessions_in_range(first, last)}
        return len(expected - actual_dates)

    expected_ms = interval_seconds * 1000
    gaps = 0
    for previous, current in zip(bars, bars[1:]):
        previous_ts = _utc_timestamp(int(previous["time"]))
        current_ts = _utc_timestamp(int(current["time"]))
        if _session_label_for_timestamp(calendar, previous_ts) != _session_label_for_timestamp(calendar, current_ts):
            continue
        previous_segment = _intraday_segment(calendar, previous_ts)
        current_segment = _intraday_segment(calendar, current_ts)
        if previous_segment is None or current_segment is None or previous_segment[0] != current_segment[0]:
            continue
        delta = int(current["time"]) - int(previous["time"])
        if delta > expected_ms * 1.5:
            gaps += max(1, int(round(delta / expected_ms)) - 1)
    return gaps
