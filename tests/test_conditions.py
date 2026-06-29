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

    def test_sma_cross_falls_back_to_comparison_without_enough_history(self) -> None:
        # Only `window` closes available -> cannot compute previous-day SMA, so
        # it falls back to a plain current-price vs SMA comparison.
        condition = Condition(id="sma", type="sma_cross", operator=">=", window=3)
        result = evaluate_condition(self.stock, condition, 12, [8, 10, 11], self.now)
        self.assertTrue(result.matched)
        self.assertEqual(result.threshold, 9.666666666666666)

    def test_sma_cross_upward_break_matches(self) -> None:
        # Previous close (9) below previous SMA (10); current price (12) at/above
        # today's SMA (~9.67) -> genuine upward cross.
        condition = Condition(id="sma", type="sma_cross", operator=">=", window=3)
        result = evaluate_condition(self.stock, condition, 12, [10, 10, 10, 9], self.now)
        self.assertTrue(result.matched)

    def test_sma_cross_no_match_when_already_above(self) -> None:
        # Previous close (11) already above previous SMA (10) -> no upward cross,
        # even though current price is above today's SMA.
        condition = Condition(id="sma", type="sma_cross", operator=">=", window=3)
        result = evaluate_condition(self.stock, condition, 12, [10, 10, 10, 11], self.now)
        self.assertFalse(result.matched)

    def test_sma_cross_downward_break_matches(self) -> None:
        # Previous close (11) above previous SMA (10); current price (9) at/below
        # today's SMA (~10.33) -> genuine downward cross.
        condition = Condition(id="sma", type="sma_cross", operator="<=", window=3)
        result = evaluate_condition(self.stock, condition, 9, [10, 10, 10, 11], self.now)
        self.assertTrue(result.matched)


if __name__ == "__main__":
    unittest.main()
