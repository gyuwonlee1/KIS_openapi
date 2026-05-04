from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


SUPPORTED_MARKETS = {"KR", "US"}
SUPPORTED_CONDITION_TYPES = {"price", "sma_cross"}
SUPPORTED_OPERATORS = {">=", "<="}
SUPPORTED_US_EXCHANGES = {"NASD", "NASDAQ", "NAS", "NYSE", "NYS", "AMEX", "AMS"}


@dataclass(frozen=True)
class Condition:
    id: str
    type: str
    operator: str
    label: str | None = None
    target: float | None = None
    window: int | None = None
    cooldown_minutes: int | None = None
    delete_after_alert: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], stock_key: str, index: int) -> "Condition":
        condition_type = str(data.get("type", "")).strip()
        operator = str(data.get("operator", "")).strip()
        condition_id = str(data.get("id") or f"{stock_key}-{condition_type}-{index}").strip()

        errors: list[str] = []
        if not condition_id:
            errors.append("condition id is required")
        if condition_type not in SUPPORTED_CONDITION_TYPES:
            errors.append(f"unsupported condition type: {condition_type}")
        if operator not in SUPPORTED_OPERATORS:
            errors.append(f"unsupported operator: {operator}")

        target = _optional_float(data.get("target"), "target", errors)
        window = _optional_int(data.get("window"), "window", errors)
        cooldown = _optional_int(data.get("cooldown_minutes"), "cooldown_minutes", errors)
        delete_after_alert = bool(data.get("delete_after_alert", False))

        if condition_type == "price" and target is None:
            errors.append("price condition requires target")
        if condition_type == "sma_cross":
            if window is None:
                errors.append("sma_cross condition requires window")
            elif window <= 0:
                errors.append("sma_cross window must be positive")

        if cooldown is not None and cooldown < 0:
            errors.append("cooldown_minutes must be zero or positive")
        if errors:
            raise ValueError(f"invalid condition {condition_id}: {'; '.join(errors)}")

        return cls(
            id=condition_id,
            type=condition_type,
            operator=operator,
            label=data.get("label"),
            target=target,
            window=window,
            cooldown_minutes=cooldown,
            delete_after_alert=delete_after_alert,
        )


@dataclass(frozen=True)
class Stock:
    name: str
    ticker: str
    market: str
    exchange: str | None = None
    enabled: bool = True
    conditions: list[Condition] = field(default_factory=list)

    @property
    def key(self) -> str:
        if self.market == "US" and self.exchange:
            return f"{self.market}:{self.exchange}:{self.ticker}"
        return f"{self.market}:{self.ticker}"

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> "Stock":
        name = str(data.get("name", "")).strip()
        ticker = str(data.get("ticker", "")).strip().upper()
        market = str(data.get("market", "")).strip().upper()
        exchange = data.get("exchange")
        exchange_value = str(exchange).strip().upper() if exchange else None
        enabled = bool(data.get("enabled", True))

        errors: list[str] = []
        if not name:
            errors.append("name is required")
        if not ticker:
            errors.append("ticker is required")
        if market not in SUPPORTED_MARKETS:
            errors.append(f"unsupported market: {market}")
        if market == "US" and not exchange_value:
            errors.append("US stock requires exchange")
        if exchange_value and exchange_value not in SUPPORTED_US_EXCHANGES:
            errors.append(f"unsupported US exchange: {exchange_value}")

        condition_items = data.get("conditions")
        if not isinstance(condition_items, list):
            errors.append("conditions must be a list")

        if errors:
            raise ValueError(f"invalid stock at index {index}: {'; '.join(errors)}")

        stock_key = f"{market}:{exchange_value + ':' if exchange_value else ''}{ticker}"
        conditions = [
            Condition.from_dict(item, stock_key, condition_index)
            for condition_index, item in enumerate(condition_items or [])
        ]
        return cls(
            name=name,
            ticker=ticker,
            market=market,
            exchange=exchange_value,
            enabled=enabled,
            conditions=conditions,
        )


@dataclass(frozen=True)
class PriceQuote:
    stock: Stock
    price: float
    raw: dict[str, Any]


@dataclass(frozen=True)
class ConditionResult:
    stock: Stock
    condition: Condition
    matched: bool
    current_price: float
    threshold: float
    detail: str
    evaluated_at: datetime

    @property
    def state_key(self) -> str:
        return f"{self.stock.key}:{self.condition.id}"


@dataclass(frozen=True)
class Alert:
    result: ConditionResult
    is_reentry: bool


def _optional_float(value: Any, field_name: str, errors: list[str]) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be numeric")
        return None


def _optional_int(value: Any, field_name: str, errors: list[str]) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be an integer")
        return None
