from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number, got {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    opend_host: str = os.getenv("QRDESK_OPEND_HOST", "127.0.0.1")
    opend_port: int = _env_int("QRDESK_OPEND_PORT", 11111)
    gateway_host: str = os.getenv("QRDESK_GATEWAY_HOST", "127.0.0.1")
    gateway_port: int = _env_int("QRDESK_GATEWAY_PORT", 8787)
    query_connect_timeout: float = _env_float("QRDESK_QUERY_CONNECT_TIMEOUT", 4.0)
    history_max_pages: int = _env_int("QRDESK_HISTORY_MAX_PAGES", 30)
    cors_origins_raw: str = os.getenv("QRDESK_ALLOWED_ORIGINS", "*")

    @property
    def cors_origins(self) -> list[str]:
        values = [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]
        return values or ["*"]


settings = Settings()
