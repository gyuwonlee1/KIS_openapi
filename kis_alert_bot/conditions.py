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
    elif condition.type == "sma_cross":
        if condition.window is None:
            raise ValueError(f"{condition.id} is missing window")
        if daily_closes is None:
            raise ValueError(f"{condition.id} requires daily closes")
        threshold = simple_moving_average(daily_closes, condition.window)
        detail = f"SMA{condition.window} {condition.operator} {threshold:g}"
    else:
        raise ValueError(f"unsupported condition type: {condition.type}")

    matched = _compare(current_price, condition.operator, threshold)
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
