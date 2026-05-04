from __future__ import annotations

import unittest
from datetime import datetime, timezone

from kis_alert_bot.conditions import evaluate_condition
from kis_alert_bot.models import Condition, Stock


class ConditionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stock = Stock(name="Samsung", ticker="005930", market="KR")
        self.now = datetime(2026, 5, 4, tzinfo=timezone.utc)

    def test_price_greater_equal(self) -> None:
        condition = Condition(id="target", type="price", operator=">=", target=100)
        result = evaluate_condition(self.stock, condition, 101, None, self.now)
        self.assertTrue(result.matched)

    def test_price_less_equal(self) -> None:
        condition = Condition(id="target", type="price", operator="<=", target=100)
        result = evaluate_condition(self.stock, condition, 99, None, self.now)
        self.assertTrue(result.matched)

    def test_sma_cross_uses_current_price_against_sma(self) -> None:
        condition = Condition(id="sma", type="sma_cross", operator=">=", window=3)
        result = evaluate_condition(self.stock, condition, 12, [8, 10, 11], self.now)
        self.assertTrue(result.matched)
        self.assertEqual(result.threshold, 9.666666666666666)


if __name__ == "__main__":
    unittest.main()
