from __future__ import annotations

import unittest
from datetime import datetime, timezone

from main import _evaluate_stock
from kis_alert_bot.models import Condition, ConditionResult, PriceQuote, Stock
from kis_alert_bot.state import AlertStateStore


class FakeClient:
    def __init__(self) -> None:
        self.current_price_calls = 0

    def get_current_price(self, stock: Stock) -> PriceQuote:
        self.current_price_calls += 1
        return PriceQuote(stock=stock, price=101, raw={})

    def get_daily_closes(self, stock: Stock) -> list[float]:
        return [90, 95, 100]


class MainEvaluationTests(unittest.TestCase):
    def test_completed_conditions_skip_price_fetch(self) -> None:
        stock = Stock(
            name="Samsung",
            ticker="005930",
            market="KR",
            conditions=[
                Condition(
                    id="target",
                    type="price",
                    operator=">=",
                    target=100,
                    delete_after_alert=True,
                )
            ],
        )
        state = AlertStateStore(path="unused")
        result = ConditionResult(
            stock,
            stock.conditions[0],
            True,
            101,
            100,
            "target >= 100",
            datetime(2026, 5, 4, tzinfo=timezone.utc),
        )
        state.update_result(result)
        client = FakeClient()

        alerts = _evaluate_stock(client, stock, state)

        self.assertEqual(alerts, [])
        self.assertEqual(client.current_price_calls, 0)


if __name__ == "__main__":
    unittest.main()
