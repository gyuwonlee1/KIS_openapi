from __future__ import annotations

import json
import unittest
import uuid

from datetime import datetime, timezone
from pathlib import Path

from kis_alert_bot.models import Alert, ConditionResult
from kis_alert_bot.portfolio import parse_portfolio, remove_alerted_conditions


def temporary_path(name: str) -> Path:
    base = Path(".tmp-tests")
    base.mkdir(exist_ok=True)
    return base / f"{name}-{uuid.uuid4().hex}.json"


class PortfolioTests(unittest.TestCase):
    def test_loads_valid_portfolio(self) -> None:
        stocks = parse_portfolio(
            {
                "stocks": [
                    {
                        "name": "Apple",
                        "ticker": "AAPL",
                        "market": "US",
                        "exchange": "NASD",
                        "conditions": [
                            {
                                "id": "price",
                                "type": "price",
                                "operator": ">=",
                                "target": 200,
                            }
                        ],
                    }
                ]
            }
        )

        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0].exchange, "NASD")
        self.assertFalse(stocks[0].conditions[0].delete_after_alert)

    def test_loads_delete_after_alert(self) -> None:
        stocks = parse_portfolio(
            {
                "stocks": [
                    {
                        "name": "Samsung",
                        "ticker": "005930",
                        "market": "KR",
                        "conditions": [
                            {
                                "id": "price",
                                "type": "price",
                                "operator": ">=",
                                "target": 80000,
                                "delete_after_alert": True,
                            }
                        ],
                    }
                ]
            }
        )

        self.assertTrue(stocks[0].conditions[0].delete_after_alert)

    def test_loads_stock_without_conditions(self) -> None:
        stocks = parse_portfolio(
            {
                "stocks": [
                    {
                        "name": "Samsung",
                        "ticker": "005930",
                        "market": "KR",
                        "conditions": [],
                    }
                ]
            }
        )

        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0].conditions, [])

    def test_removes_only_alerted_completed_condition(self) -> None:
        portfolio = {
            "stocks": [
                {
                    "name": "Samsung",
                    "ticker": "005930",
                    "market": "KR",
                    "conditions": [
                        {
                            "id": "target",
                            "type": "price",
                            "operator": ">=",
                            "target": 80000,
                            "delete_after_alert": True,
                        },
                        {
                            "id": "sma60",
                            "type": "sma_cross",
                            "operator": ">=",
                            "window": 60,
                            "delete_after_alert": True,
                        },
                    ],
                }
            ]
        }
        stock = parse_portfolio(portfolio)[0]
        result = ConditionResult(
            stock=stock,
            condition=stock.conditions[0],
            matched=True,
            current_price=81000,
            threshold=80000,
            detail="target >= 80000",
            evaluated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        )

        path = temporary_path("portfolio")
        try:
            path.write_text(
                json.dumps(portfolio, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            removed_count = remove_alerted_conditions(path, [Alert(result, is_reentry=False)])
            stocks = parse_portfolio(json.loads(path.read_text(encoding="utf-8")))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(removed_count, 1)
        self.assertEqual([condition.id for condition in stocks[0].conditions], ["sma60"])

    def test_remove_alerted_conditions_keeps_stock_when_last_condition_removed(self) -> None:
        portfolio = {
            "stocks": [
                {
                    "name": "Samsung",
                    "ticker": "005930",
                    "market": "KR",
                    "conditions": [
                        {
                            "id": "target",
                            "type": "price",
                            "operator": ">=",
                            "target": 80000,
                            "delete_after_alert": True,
                        }
                    ],
                }
            ]
        }
        stock = parse_portfolio(portfolio)[0]
        result = ConditionResult(
            stock=stock,
            condition=stock.conditions[0],
            matched=True,
            current_price=81000,
            threshold=80000,
            detail="target >= 80000",
            evaluated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        )

        path = temporary_path("portfolio")
        try:
            path.write_text(
                json.dumps(portfolio, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            removed_count = remove_alerted_conditions(path, [Alert(result, is_reentry=False)])
            stocks = parse_portfolio(json.loads(path.read_text(encoding="utf-8")))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(removed_count, 1)
        self.assertEqual(stocks[0].conditions, [])

    def test_rejects_invalid_operator(self) -> None:
        with self.assertRaises(ValueError):
            parse_portfolio(
                {
                    "stocks": [
                        {
                            "name": "Samsung",
                            "ticker": "005930",
                            "market": "KR",
                            "conditions": [
                                {
                                    "id": "bad",
                                    "type": "price",
                                    "operator": ">",
                                    "target": 100,
                                }
                            ],
                        }
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
