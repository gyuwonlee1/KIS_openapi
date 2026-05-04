from __future__ import annotations

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
    condition = alert.result.condition
    color = GREEN if condition.operator == ">=" else RED
    return {
        "title": _alert_title(alert),
        "description": _condition_text(alert),
        "color": color,
    }


def build_error_embed(errors: list[str]) -> dict[str, Any]:
    visible_errors = errors[:10]
    extra_count = max(0, len(errors) - len(visible_errors))
    description = "\n".join(f"- {error}" for error in visible_errors)
    if extra_count:
        description += f"\n- 외 {extra_count}건"
    return {
        "title": "KIS 알림 봇 오류",
        "description": description,
        "color": YELLOW,
    }


def _alert_title(alert: Alert) -> str:
    stock = alert.result.stock
    return f"{stock.name} ({stock.ticker})"


def _condition_text(alert: Alert) -> str:
    result = alert.result
    condition = result.condition
    operator = _operator_label(condition.operator)

    if condition.type == "price":
        threshold = _format_price(result.threshold, result.stock.market)
        return f"현재가가 {threshold} {operator}일 때"
    if condition.type == "sma_cross":
        window = condition.window or 0
        return f"현재가가 {window}일 이동평균선 {operator}일 때"
    return result.detail


def _operator_label(operator: str) -> str:
    if operator == ">=":
        return "이상"
    if operator == "<=":
        return "이하"
    return operator


def _format_price(value: float, market: str) -> str:
    if market == "KR":
        return f"{value:,.0f}원"
    if market == "US":
        return f"${value:,.2f}"
    return f"{value:g}"
