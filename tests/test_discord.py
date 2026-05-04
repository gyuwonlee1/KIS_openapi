from __future__ import annotations

import unittest
from datetime import datetime, timezone

from kis_alert_bot.discord import build_alert_embed, build_error_embed
from kis_alert_bot.models import Alert, Condition, ConditionResult, Stock


class DiscordTests(unittest.TestCase):
    def test_price_alert_embed_is_korean(self) -> None:
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
        self.assertEqual(embed["title"], "삼성전자 목표가 도달")
        self.assertEqual(embed["fields"][0]["name"], "종목")
        self.assertEqual(embed["fields"][1]["value"], "국내")
        self.assertEqual(embed["fields"][2]["value"], "81,000원")
        self.assertIn("80,000원 이상", embed["fields"][4]["value"])

    def test_sma_alert_embed_is_korean(self) -> None:
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
        self.assertEqual(embed["title"], "삼성전자 60일 이동평균선 돌파 재감지")
        self.assertIn("60일 이동평균선(80,500원) 이상", embed["fields"][4]["value"])

    def test_us_price_format(self) -> None:
        stock = Stock(name="애플", ticker="AAPL", market="US", exchange="NASD")
        condition = Condition(id="target", type="price", operator="<=", target=180)
        result = ConditionResult(
            stock=stock,
            condition=condition,
            matched=True,
            current_price=179.125,
            threshold=180,
            detail="target <= 180",
            evaluated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        )
        embed = build_alert_embed(Alert(result=result, is_reentry=False))
        self.assertEqual(embed["title"], "애플 하락 기준가 도달")
        self.assertEqual(embed["fields"][1]["value"], "미국/NASD")
        self.assertEqual(embed["fields"][2]["value"], "$179.12")
        self.assertIn("$180.00 이하", embed["fields"][4]["value"])

    def test_error_embed_limits_visible_errors(self) -> None:
        embed = build_error_embed([f"error {index}" for index in range(12)])
        self.assertEqual(embed["title"], "KIS 알림 봇 오류")
        self.assertIn("외 2건", embed["description"])

    def test_delete_after_alert_embed_mentions_completion(self) -> None:
        stock = Stock(name="삼성전자", ticker="005930", market="KR")
        condition = Condition(
            id="target",
            type="price",
            operator=">=",
            target=80000,
            delete_after_alert=True,
        )
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

        self.assertIn("완료 처리", [field["name"] for field in embed["fields"]])
        self.assertIn("1회 알림 후 완료", str(embed["fields"]))


if __name__ == "__main__":
    unittest.main()
