from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import main
from kis_alert_bot.config import Settings
from main import _evaluate_stock
from kis_alert_bot.models import Condition, ConditionResult, PriceQuote, Stock
from kis_alert_bot.state import AlertStateStore


def temporary_path(name: str) -> Path:
    base = Path(".tmp-tests")
    base.mkdir(exist_ok=True)
    return base / f"{name}-{uuid.uuid4().hex}.json"


class FakeClient:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.current_price_calls = 0

    def get_current_price(self, stock: Stock) -> PriceQuote:
        self.current_price_calls += 1
        return PriceQuote(stock=stock, price=101, raw={})

    def get_daily_closes(self, stock: Stock) -> list[float]:
        return [90, 95, 100]


class FailingNotifier:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def send_alerts(self, alerts: list[object]) -> None:
        if alerts:
            raise RuntimeError("discord failed")

    def send_error_summary(self, _errors: list[str]) -> None:
        pass


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

    def test_stock_without_conditions_skips_price_fetch(self) -> None:
        stock = Stock(name="Samsung", ticker="005930", market="KR", conditions=[])
        state = AlertStateStore(path="unused")
        client = FakeClient()

        alerts = _evaluate_stock(client, stock, state)

        self.assertEqual(alerts, [])
        self.assertEqual(client.current_price_calls, 0)

    def test_discord_failure_does_not_remove_condition_or_save_state(self) -> None:
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
                            "target": 100,
                            "delete_after_alert": True,
                        }
                    ],
                }
            ]
        }
        portfolio_path = temporary_path("portfolio")
        state_path = temporary_path("state")
        try:
            portfolio_path.write_text(json.dumps(portfolio), encoding="utf-8")
            settings = Settings(
                app_key="key",
                app_secret="secret",
                discord_webhook_url="https://example.invalid",
                portfolio_path=str(portfolio_path),
                state_path=str(state_path),
                market_hours_enabled=False,
            )

            with (
                patch.object(main.Settings, "from_env", return_value=settings),
                patch.object(main, "DiscordNotifier", FailingNotifier),
                patch.object(main, "KISClient", FakeClient),
            ):
                exit_code = main.run()

            saved = json.loads(portfolio_path.read_text(encoding="utf-8"))
            state_exists = state_path.exists()
        finally:
            portfolio_path.unlink(missing_ok=True)
            state_path.unlink(missing_ok=True)

        self.assertEqual(exit_code, 1)
        self.assertEqual(saved["stocks"][0]["conditions"][0]["id"], "target")
        self.assertFalse(state_exists)


if __name__ == "__main__":
    unittest.main()
