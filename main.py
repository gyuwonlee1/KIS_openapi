from __future__ import annotations

from datetime import datetime, timezone

from kis_alert_bot.conditions import evaluate_condition
from kis_alert_bot.config import Settings
from kis_alert_bot.discord import DiscordNotifier
from kis_alert_bot.kis_client import KISClient
from kis_alert_bot.market_hours import is_market_open
from kis_alert_bot.models import Alert, Stock
from kis_alert_bot.portfolio import load_portfolio
from kis_alert_bot.state import AlertStateStore


def run() -> int:
    errors: list[str] = []
    alerts: list[Alert] = []
    notifier: DiscordNotifier | None = None

    try:
        settings = Settings.from_env()
        notifier = DiscordNotifier(settings.discord_webhook_url, settings.http_timeout_seconds)
        stocks = load_portfolio(settings.portfolio_path)
        state = AlertStateStore.load(settings.state_path)
        client = KISClient(
            app_key=settings.app_key,
            app_secret=settings.app_secret,
            base_url=settings.base_url,
            min_interval_seconds=settings.min_interval_seconds,
            overseas_interval_seconds=settings.overseas_interval_seconds,
            timeout_seconds=settings.http_timeout_seconds,
        )

        for stock in stocks:
            if not stock.enabled:
                continue
            if settings.market_hours_enabled and not is_market_open(stock):
                continue
            try:
                alerts.extend(_evaluate_stock(client, stock, state))
            except Exception as exc:
                errors.append(f"{stock.name} ({stock.ticker}): {exc}")

        state.save()
        notifier.send_alerts(alerts)
        notifier.send_error_summary(errors)
    except Exception as exc:
        errors.append(str(exc))
        if notifier is not None:
            notifier.send_error_summary(errors)
        else:
            print("KIS alert bot failed before Discord setup:")
            for error in errors:
                print(f"- {error}")
        return 1

    return 1 if errors else 0


def _evaluate_stock(client: KISClient, stock: Stock, state: AlertStateStore) -> list[Alert]:
    quote = client.get_current_price(stock)
    daily_closes: list[float] | None = None
    now = datetime.now(timezone.utc)
    alerts: list[Alert] = []

    for condition in stock.conditions:
        if condition.type == "sma_cross" and daily_closes is None:
            daily_closes = client.get_daily_closes(stock)
        result = evaluate_condition(
            stock=stock,
            condition=condition,
            current_price=quote.price,
            daily_closes=daily_closes,
            evaluated_at=now,
        )
        alert = state.update_result(result)
        if alert is not None:
            alerts.append(alert)

    return alerts


if __name__ == "__main__":
    raise SystemExit(run())
