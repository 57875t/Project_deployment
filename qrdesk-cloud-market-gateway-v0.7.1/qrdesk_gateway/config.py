from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    environment: str
    allowed_origins: tuple[str, ...]
    request_timeout_seconds: float
    cache_ttl_seconds: int
    massive_api_key: str | None
    massive_base_url: str
    massive_recency: str
    eodhd_api_token: str | None
    eodhd_base_url: str
    eodhd_recency: str
    max_requests_per_minute: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            environment=os.getenv("QRDESK_ENV", "development"),
            allowed_origins=_csv(os.getenv("QRDESK_ALLOWED_ORIGINS", "*")) or ("*",),
            request_timeout_seconds=_float("QRDESK_PROVIDER_TIMEOUT_SECONDS", 12.0),
            cache_ttl_seconds=max(0, _int("QRDESK_CACHE_TTL_SECONDS", 20)),
            massive_api_key=os.getenv("MASSIVE_API_KEY") or None,
            massive_base_url=os.getenv("MASSIVE_BASE_URL", "https://api.massive.com").rstrip("/"),
            massive_recency=os.getenv("MASSIVE_RECENCY", "plan-dependent"),
            eodhd_api_token=os.getenv("EODHD_API_TOKEN") or None,
            eodhd_base_url=os.getenv("EODHD_BASE_URL", "https://eodhd.com").rstrip("/"),
            eodhd_recency=os.getenv("EODHD_RECENCY", "delayed-historical"),
            max_requests_per_minute=max(1, _int("QRDESK_MAX_REQUESTS_PER_MINUTE", 60)),
        )


settings = Settings.from_env()
