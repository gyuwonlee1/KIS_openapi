from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from kis_alert_bot.models import Condition, ConditionResult, Stock
from kis_alert_bot.state import AlertStateStore


class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stock = Stock(name="Samsung", ticker="005930", market="KR")
        self.condition = Condition(id="target", type="price", operator=">=", target=100)
        self.store = AlertStateStore(path="unused")

    def result(self, matched: bool, when: datetime | None = None) -> ConditionResult:
        return ConditionResult(
            stock=self.stock,
            condition=self.condition,
            matched=matched,
            current_price=101 if matched else 99,
            threshold=100,
            detail="target >= 100",
            evaluated_at=when or datetime(2026, 5, 4, tzinfo=timezone.utc),
        )

    def test_alerts_only_on_false_to_true(self) -> None:
        self.assertIsNotNone(self.store.update_result(self.result(True)))
        self.assertIsNone(self.store.update_result(self.result(True)))
        self.assertIsNone(self.store.update_result(self.result(False)))
        self.assertIsNotNone(self.store.update_result(self.result(True)))

    def test_cooldown_can_repeat_while_true(self) -> None:
        condition = Condition(
            id="target",
            type="price",
            operator=">=",
            target=100,
            cooldown_minutes=30,
        )
        base = datetime(2026, 5, 4, tzinfo=timezone.utc)
        first = ConditionResult(self.stock, condition, True, 101, 100, "target >= 100", base)
        second = ConditionResult(
            self.stock,
            condition,
            True,
            101,
            100,
            "target >= 100",
            base + timedelta(minutes=31),
        )
        self.assertIsNotNone(self.store.update_result(first))
        self.assertIsNotNone(self.store.update_result(second))


if __name__ == "__main__":
    unittest.main()
