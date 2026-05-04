from __future__ import annotations

from datetime import timezone
from typing import Any

from kis_alert_bot.models import Alert


GREEN = 0x2ECC71
RED = 0xE74C3C
YELLOW = 0xF1C40F


class DiscordNotifier:
    def __init__(self, webhook_url: str, timeout_seconds: float = 10.0) -> None:
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    def send_alerts(self, alerts: list[Alert]) -> None:
        if not alerts:
            return
        payload = {"embeds": [build_alert_embed(alert) for alert in alerts]}
        self._post(payload)

    def send_error_summary(self, errors: list[str]) -> None:
        if not errors:
            return
        payload = {"embeds": [build_error_embed(errors)]}
        self._post(payload)

    def _post(self, payload: dict[str, Any]) -> None:
        import requests

        response = requests.post(self.webhook_url, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()


def build_alert_embed(alert: Alert) -> dict[str, Any]:
    result = alert.result
    condition = result.condition
    title = condition.label or condition.id
    color = GREEN if condition.operator == ">=" else RED
    if alert.is_reentry:
        title = f"{title} (re-entry)"

    timestamp = result.evaluated_at.astimezone(timezone.utc).isoformat()
    return {
        "title": title,
        "description": f"{result.stock.name} `{result.stock.ticker}` matched `{condition.type}`",
        "color": color,
        "timestamp": timestamp,
        "fields": [
            {"name": "Market", "value": _market_label(result.stock), "inline": True},
            {"name": "Current", "value": f"{result.current_price:g}", "inline": True},
            {"name": "Threshold", "value": f"{result.threshold:g}", "inline": True},
            {"name": "Condition", "value": result.detail, "inline": False},
        ],
    }


def build_error_embed(errors: list[str]) -> dict[str, Any]:
    visible_errors = errors[:10]
    extra_count = max(0, len(errors) - len(visible_errors))
    description = "\n".join(f"- {error}" for error in visible_errors)
    if extra_count:
        description += f"\n- ... and {extra_count} more"
    return {
        "title": "KIS alert bot errors",
        "description": description,
        "color": YELLOW,
    }


def _market_label(stock: Any) -> str:
    if stock.market == "US" and stock.exchange:
        return f"{stock.market}/{stock.exchange}"
    return stock.market
