from __future__ import annotations

import json
from pathlib import Path

from kis_alert_bot.models import Alert, Stock


def load_portfolio(path: str | Path) -> list[Stock]:
    portfolio_path = Path(path)
    with portfolio_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return parse_portfolio(data)


def parse_portfolio(data: object) -> list[Stock]:
    if not isinstance(data, dict):
        raise ValueError("portfolio root must be an object")
    stocks_data = data.get("stocks")
    if not isinstance(stocks_data, list):
        raise ValueError("portfolio must contain a stocks list")

    stocks = [Stock.from_dict(item, index) for index, item in enumerate(stocks_data)]
    duplicate_conditions: set[str] = set()
    seen_conditions: set[str] = set()
    for stock in stocks:
        for condition in stock.conditions:
            key = f"{stock.key}:{condition.id}"
            if key in seen_conditions:
                duplicate_conditions.add(key)
            seen_conditions.add(key)
    if duplicate_conditions:
        joined = ", ".join(sorted(duplicate_conditions))
        raise ValueError(f"duplicate condition keys: {joined}")
    return stocks


def remove_alerted_conditions(path: str | Path, alerts: list[Alert]) -> int:
    completed_keys = {
        alert.result.state_key
        for alert in alerts
        if alert.result.condition.delete_after_alert
    }
    if not completed_keys:
        return 0

    portfolio_path = Path(path)
    with portfolio_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not isinstance(data.get("stocks"), list):
        raise ValueError("portfolio must contain a stocks list")

    removed_count = 0
    for stock_data in data["stocks"]:
        if not isinstance(stock_data, dict):
            continue
        stock_key = _stock_key_from_dict(stock_data)
        conditions = stock_data.get("conditions")
        if not isinstance(conditions, list):
            continue
        kept_conditions = []
        for condition in conditions:
            condition_id = str(condition.get("id", "")).strip() if isinstance(condition, dict) else ""
            if condition_id and f"{stock_key}:{condition_id}" in completed_keys:
                removed_count += 1
                continue
            kept_conditions.append(condition)
        stock_data["conditions"] = kept_conditions

    if removed_count:
        with portfolio_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
    return removed_count


def _stock_key_from_dict(data: dict[str, object]) -> str:
    market = str(data.get("market", "")).strip().upper()
    ticker = str(data.get("ticker", "")).strip().upper()
    exchange = data.get("exchange")
    exchange_value = str(exchange).strip().upper() if exchange else ""
    if market == "US" and exchange_value:
        return f"{market}:{exchange_value}:{ticker}"
    return f"{market}:{ticker}"
