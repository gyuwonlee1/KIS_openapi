from __future__ import annotations

from datetime import datetime

from kis_alert_bot.indicators import simple_moving_average
from kis_alert_bot.models import Condition, ConditionResult, Stock


def evaluate_condition(
    stock: Stock,
    condition: Condition,
    current_price: float,
    daily_closes: list[float] | None,
    evaluated_at: datetime,
) -> ConditionResult:
    if condition.type == "price":
        if condition.target is None:
            raise ValueError(f"{condition.id} is missing target")
        threshold = condition.target
        detail = f"target {condition.operator} {threshold:g}"
        matched = _compare(current_price, condition.operator, threshold)
    elif condition.type == "sma_cross":
        if condition.window is None:
            raise ValueError(f"{condition.id} is missing window")
        if daily_closes is None:
            raise ValueError(f"{condition.id} requires daily closes")
        threshold = simple_moving_average(daily_closes, condition.window)
        detail = f"SMA{condition.window} {condition.operator} {threshold:g}"
        matched = _sma_cross_matched(
            condition.operator, daily_closes, condition.window, current_price, threshold
        )
    else:
        raise ValueError(f"unsupported condition type: {condition.type}")

    return ConditionResult(
        stock=stock,
        condition=condition,
        matched=matched,
        current_price=current_price,
        threshold=threshold,
        detail=detail,
        evaluated_at=evaluated_at,
    )


def _compare(current_price: float, operator: str, threshold: float) -> bool:
    if operator == ">=":
        return current_price >= threshold
    if operator == "<=":
        return current_price <= threshold
    raise ValueError(f"unsupported operator: {operator}")


def _sma_cross_matched(
    operator: str,
    daily_closes: list[float],
    window: int,
    current_price: float,
    today_sma: float,
) -> bool:
    """Detect an actual cross, not just current price vs SMA.

    `>=` (upward break): yesterday's close was below its SMA AND the current
    price is now at/above today's SMA.
    `<=` (downward break): yesterday's close was above its SMA AND the current
    price is now at/below today's SMA.

    Falls back to a plain comparison when there is not enough history to compute
    the previous-day SMA (e.g. newly listed stocks), preserving prior behavior.
    """
    if len(daily_closes) < window + 1:
        return _compare(current_price, operator, today_sma)

    prev_sma = simple_moving_average(daily_closes[:-1], window)
    prev_close = daily_closes[-1]
    if operator == ">=":
        return prev_close < prev_sma and current_price >= today_sma
    if operator == "<=":
        return prev_close > prev_sma and current_price <= today_sma
    raise ValueError(f"unsupported operator: {operator}")
