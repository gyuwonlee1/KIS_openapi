from __future__ import annotations

from datetime import timezone
from typing import Any
from zoneinfo import ZoneInfo

from kis_alert_bot.models import Alert


GREEN = 0x2ECC71
RED = 0xE74C3C
YELLOW = 0xF1C40F
KST = ZoneInfo("Asia/Seoul")


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
    title = _alert_title(alert)
    color = GREEN if condition.operator == ">=" else RED

    timestamp = result.evaluated_at.astimezone(timezone.utc).isoformat()
    return {
        "title": title,
        "description": _alert_description(alert),
        "color": color,
        "timestamp": timestamp,
        "fields": [
            {"name": "종목", "value": f"{result.stock.name} (`{result.stock.ticker}`)", "inline": True},
            {"name": "시장", "value": _market_label(result.stock), "inline": True},
            {
                "name": "현재가",
                "value": _format_price(result.current_price, result.stock.market),
                "inline": True,
            },
            {
                "name": "기준값",
                "value": _format_price(result.threshold, result.stock.market),
                "inline": True,
            },
            {"name": "조건", "value": _condition_text(alert), "inline": False},
            *_completion_field(alert),
            {"name": "감지 시각", "value": _format_kst(result.evaluated_at), "inline": False},
        ],
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


def _market_label(stock: Any) -> str:
    if stock.market == "KR":
        return "국내"
    if stock.market == "US" and stock.exchange:
        return f"미국/{stock.exchange}"
    return stock.market


def _alert_title(alert: Alert) -> str:
    result = alert.result
    condition = result.condition
    prefix = f"{result.stock.name} "
    suffix = " 재감지" if alert.is_reentry else ""

    if condition.type == "price":
        if condition.operator == ">=":
            return f"{prefix}목표가 도달{suffix}"
        return f"{prefix}하락 기준가 도달{suffix}"
    if condition.type == "sma_cross":
        window = condition.window or 0
        action = "돌파" if condition.operator == ">=" else "이탈"
        return f"{prefix}{window}일 이동평균선 {action}{suffix}"
    return f"{prefix}알림 조건 충족{suffix}"


def _alert_description(alert: Alert) -> str:
    if alert.is_reentry:
        return "조건을 벗어난 뒤 다시 충족되어 알림을 보냅니다."
    return "설정한 조건을 충족해 알림을 보냅니다."


def _condition_text(alert: Alert) -> str:
    result = alert.result
    condition = result.condition
    operator = _operator_label(condition.operator)

    if condition.type == "price":
        threshold = _format_price(result.threshold, result.stock.market)
        return f"현재가가 {threshold} {operator}일 때"
    if condition.type == "sma_cross":
        window = condition.window or 0
        threshold = _format_price(result.threshold, result.stock.market)
        return f"현재가가 {window}일 이동평균선({threshold}) {operator}일 때"
    return result.detail


def _completion_field(alert: Alert) -> list[dict[str, Any]]:
    if not alert.result.condition.delete_after_alert:
        return []
    return [
        {
            "name": "완료 처리",
            "value": "이 조건은 1회 알림 후 완료 처리되었습니다.",
            "inline": False,
        }
    ]


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


def _format_kst(value: Any) -> str:
    return value.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")
