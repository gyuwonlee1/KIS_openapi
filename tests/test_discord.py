from __future__ import annotations

import unittest
from datetime import datetime, timezone

from kis_alert_bot.discord import build_alert_embed, build_error_embed
from kis_alert_bot.models import Alert, Condition, ConditionResult, Stock


class DiscordTests(unittest.TestCase):
    def test_alert_embed_shape(self) -> None:
        stock = Stock(name="Samsung", ticker="005930", market="KR")
        condition = Condition(id="target", type="price", operator=">=", target=100)
        result = ConditionResult(
            stock=stock,
            condition=condition,
            matched=True,
            current_price=101,
            threshold=100,
            detail="target >= 100",
            evaluated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        )
        embed = build_alert_embed(Alert(result=result, is_reentry=False))
        self.assertEqual(embed["title"], "target")
        self.assertEqual(embed["fields"][1]["value"], "101")

    def test_error_embed_limits_visible_errors(self) -> None:
        embed = build_error_embed([f"error {index}" for index in range(12)])
        self.assertIn("and 2 more", embed["description"])


if __name__ == "__main__":
    unittest.main()
