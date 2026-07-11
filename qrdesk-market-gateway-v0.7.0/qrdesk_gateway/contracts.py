from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class InstrumentMeta:
    market: str
    exchange: str
    currency: str
    timezone: str
    asset_type: str


INSTRUMENTS: dict[str, InstrumentMeta] = {
    "US.AAPL": InstrumentMeta("US", "NASDAQ", "USD", "America/New_York", "EQUITY"),
    "US.MSFT": InstrumentMeta("US", "NASDAQ", "USD", "America/New_York", "EQUITY"),
    "US.NVDA": InstrumentMeta("US", "NASDAQ", "USD", "America/New_York", "EQUITY"),
    "US.TSLA": InstrumentMeta("US", "NASDAQ", "USD", "America/New_York", "EQUITY"),
    "US.AMZN": InstrumentMeta("US", "NASDAQ", "USD", "America/New_York", "EQUITY"),
    "US.GOOGL": InstrumentMeta("US", "NASDAQ", "USD", "America/New_York", "EQUITY"),
    "US.META": InstrumentMeta("US", "NASDAQ", "USD", "America/New_York", "EQUITY"),
    "US.SPY": InstrumentMeta("US", "NYSEARCA", "USD", "America/New_York", "ETF"),
    "US.QQQ": InstrumentMeta("US", "NASDAQ", "USD", "America/New_York", "ETF"),
    "HK.00700": InstrumentMeta("HK", "HKEX", "HKD", "Asia/Hong_Kong", "EQUITY"),
    "HK.09988": InstrumentMeta("HK", "HKEX", "HKD", "Asia/Hong_Kong", "EQUITY"),
    "HK.03690": InstrumentMeta("HK", "HKEX", "HKD", "Asia/Hong_Kong", "EQUITY"),
    "SH.600519": InstrumentMeta("CN", "SSE", "CNY", "Asia/Shanghai", "EQUITY"),
    "SZ.000001": InstrumentMeta("CN", "SZSE", "CNY", "Asia/Shanghai", "EQUITY"),
    "SZ.300750": InstrumentMeta("CN", "SZSE", "CNY", "Asia/Shanghai", "EQUITY"),
}

RANGE_CONFIG: dict[str, dict[str, object]] = {
    "1d": {"interval": "5m", "points": 78, "lookback_days": 10},
    "5d": {"interval": "15m", "points": 130, "lookback_days": 18},
    "1mo": {"interval": "1h", "points": 160, "lookback_days": 50},
    "6mo": {"interval": "1d", "points": 130, "lookback_days": 230},
}

INTERVAL_SECONDS = {"5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


def meta_for(code: str) -> InstrumentMeta:
    if code in INSTRUMENTS:
        return INSTRUMENTS[code]
    prefix = code.split(".", 1)[0].upper()
    if prefix == "US":
        return InstrumentMeta("US", "US", "USD", "America/New_York", "EQUITY")
    if prefix == "HK":
        return InstrumentMeta("HK", "HKEX", "HKD", "Asia/Hong_Kong", "EQUITY")
    if prefix == "SH":
        return InstrumentMeta("CN", "SSE", "CNY", "Asia/Shanghai", "EQUITY")
    if prefix == "SZ":
        return InstrumentMeta("CN", "SZSE", "CNY", "Asia/Shanghai", "EQUITY")
    raise ValueError(f"Unsupported instrument code: {code}")


def date_window(range_key: str, selected_date: str | None, *, now: datetime | None = None) -> tuple[str, str]:
    if selected_date:
        parsed = date.fromisoformat(selected_date)
        value = parsed.isoformat()
        return value, value
    cfg = RANGE_CONFIG[range_key]
    current = (now or datetime.now(tz=ZoneInfo("UTC"))).date()
    start = current - timedelta(days=int(cfg["lookback_days"]))
    return start.isoformat(), current.isoformat()


def parse_market_time(value: object, timezone_name: str) -> int:
    if isinstance(value, (int, float)):
        numeric = float(value)
        return int(numeric if numeric > 10_000_000_000 else numeric * 1000)
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("empty market timestamp")
    formats = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")
    for fmt in formats:
        try:
            local = datetime.strptime(raw, fmt).replace(tzinfo=ZoneInfo(timezone_name))
            return int(local.timestamp() * 1000)
        except ValueError:
            continue
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return int(parsed.timestamp() * 1000)


def filter_range_bars(bars: list[dict], range_key: str, timezone_name: str) -> list[dict]:
    if not bars:
        return []
    bars = sorted({int(item["time"]): item for item in bars}.values(), key=lambda item: item["time"])
    cfg = RANGE_CONFIG[range_key]
    if range_key == "1d":
        tz = ZoneInfo(timezone_name)
        last_date = datetime.fromtimestamp(bars[-1]["time"] / 1000, tz=tz).date()
        bars = [item for item in bars if datetime.fromtimestamp(item["time"] / 1000, tz=tz).date() == last_date]
    elif range_key == "5d":
        tz = ZoneInfo(timezone_name)
        dates: list[date] = []
        for item in reversed(bars):
            d = datetime.fromtimestamp(item["time"] / 1000, tz=tz).date()
            if d not in dates:
                dates.append(d)
            if len(dates) >= 5:
                break
        allowed = set(dates)
        bars = [item for item in bars if datetime.fromtimestamp(item["time"] / 1000, tz=tz).date() in allowed]
    return bars[-int(cfg["points"]):]
