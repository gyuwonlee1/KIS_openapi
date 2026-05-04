from __future__ import annotations

import json
from pathlib import Path

from kis_alert_bot.models import Stock


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
