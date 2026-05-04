from __future__ import annotations

import unittest
from datetime import datetime, timezone

from kis_alert_bot.discord import build_alert_embed, build_error_embed
from kis_alert_bot.models import Alert, Condition, ConditionResult, Stock


class DiscordTests(unittest.TestCase):
    def test_price_alert_embed_only_shows_stock_and_condition(self) -> None:
        stock = Stock(name="삼성전자", ticker="005930", market="KR")
        condition = Condition(id="target", type="price", operator=">=", target=80000)
        result = ConditionResult(
            stock=stock,
            condition=condition,
            matched=True,
            current_price=81000,
            threshold=80000,
            detail="target >= 80000",
            evaluated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        )

        embed = build_alert_embed(Alert(result=result, is_reentry=False))

        self.assertEqual(embed["title"], "삼성전자 (005930)")
        self.assertEqual(embed["description"], "현재가가 80,000원 이상일 때")
        self.assertEqual(set(embed), {"title", "description", "color"})

    def test_sma_alert_embed_only_shows_stock_and_condition(self) -> None:
        stock = Stock(name="삼성전자", ticker="005930", market="KR")
        condition = Condition(id="sma60", type="sma_cross", operator=">=", window=60)
        result = ConditionResult(
            stock=stock,
            condition=condition,
            matched=True,
            current_price=81000,
            threshold=80500,
            detail="SMA60 >= 80500",
            evaluated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        )

        embed = build_alert_embed(Alert(result=result, is_reentry=True))

        self.assertEqual(embed["title"], "삼성전자 (005930)")
        self.assertEqual(embed["description"], "현재가가 60일 이동평균선 이상일 때")
        self.assertEqual(set(embed), {"title", "description", "color"})

    def test_us_price_format(self) -> None:
        stock = Stock(name="Alphabet Inc.", ticker="GOOGL", market="US", exchange="NASD")
        condition = Condition(id="target", type="price", operator="<=", target=400)
        result = ConditionResult(
            stock=stock,
            condition=condition,
            matched=True,
            current_price=381.18,
            threshold=400,
            detail="target <= 400",
            evaluated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        )

        embed = build_alert_embed(Alert(result=result, is_reentry=False))

        self.assertEqual(embed["title"], "Alphabet Inc. (GOOGL)")
        self.assertEqual(embed["description"], "현재가가 $400.00 이하일 때")

    def test_error_embed_limits_visible_errors(self) -> None:
        embed = build_error_embed([f"error {index}" for index in range(12)])
        self.assertEqual(embed["title"], "KIS 알림 봇 오류")
        self.assertIn("외 2건", embed["description"])


if __name__ == "__main__":
    unittest.main()
