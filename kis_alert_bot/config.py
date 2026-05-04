from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_key: str
    app_secret: str
    discord_webhook_url: str
    base_url: str = "https://openapi.koreainvestment.com:9443"
    portfolio_path: str = "portfolio.json"
    state_path: str = ".cache/kis-alerts/last_alerts.json"
    market_hours_enabled: bool = True
    min_interval_seconds: float = 0.2
    overseas_interval_seconds: float = 1.0
    http_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        app_key = _required("KIS_APP_KEY")
        app_secret = _required("KIS_APP_SECRET")
        discord_webhook_url = _required("DISCORD_WEBHOOK_URL")
        return cls(
            app_key=app_key,
            app_secret=app_secret,
            discord_webhook_url=discord_webhook_url,
            base_url=_string_env("KIS_BASE_URL", cls.base_url).rstrip("/"),
            portfolio_path=_string_env("PORTFOLIO_PATH", cls.portfolio_path),
            state_path=_string_env("STATE_PATH", cls.state_path),
            market_hours_enabled=_bool_env("MARKET_HOURS_ENABLED", True),
            min_interval_seconds=_float_env("KIS_MIN_INTERVAL_SECONDS", 0.2),
            overseas_interval_seconds=_float_env("KIS_OVERSEAS_INTERVAL_SECONDS", 1.0),
            http_timeout_seconds=_float_env("HTTP_TIMEOUT_SECONDS", 10.0),
        )


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"missing required environment variable: {name}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _string_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
