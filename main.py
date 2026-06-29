from __future__ import annotations

from datetime import datetime, timezone

from kis_alert_bot.conditions import evaluate_condition
from kis_alert_bot.config import Settings
from kis_alert_bot.discord import DiscordNotifier
from kis_alert_bot.kis_client import KISClient, TemporaryKISDataUnavailable
from kis_alert_bot.market_hours import is_market_open
from kis_alert_bot.models import Alert, Stock
from kis_alert_bot.portfolio import load_portfolio
from kis_alert_bot.state import AlertStateStore


def run() -> int:
    # Per-stock errors are transient KIS API failures: reported to Discord but
    # they must NOT fail the GitHub Actions run. Only a fatal error (config /
    # portfolio load / token / Discord send) propagates to a non-zero exit code.
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
            token_cache_path=settings.token_cache_path,
        )

        print(f"Loaded {len(stocks)} stocks from {settings.portfolio_path}")
        for stock in stocks:
            if not stock.enabled:
                print(f"Skipping disabled stock: {stock.name} ({stock.ticker})")
                continue
            if settings.market_hours_enabled and not is_market_open(stock):
                print(f"Skipping outside market hours: {stock.name} ({stock.ticker})")
                continue
            try:
                print(f"Evaluating stock: {stock.name} ({stock.ticker})")
                alerts.extend(_evaluate_stock(client, stock, state))
            except Exception as exc:
                errors.append(f"{stock.name} ({stock.ticker}): {exc}")

        notifier.send_alerts(alerts)
        # Completion is tracked via the state store's `done` flag (persisted across
        # runs); the bot no longer rewrites/commits portfolio.json. This keeps the
        # bot read-only on portfolio.json and avoids races with the web/Discord
        # editors that commit it via the GitHub API.
        state.save()
        notifier.send_error_summary(errors)
        print(f"Completed run: {len(alerts)} alerts, {len(errors)} per-stock errors")
    except Exception as exc:
        # Fatal error: setup, portfolio load, state save, or Discord send failed.
        errors.append(str(exc))
        if notifier is not None:
            notifier.send_error_summary(errors)
        else:
            print("KIS alert bot failed before Discord setup:")
            for error in errors:
                print(f"- {error}")
        return 1

    # Transient per-stock errors do not fail the run.
    return 0


def _evaluate_stock(client: KISClient, stock: Stock, state: AlertStateStore) -> list[Alert]:
    active_conditions = [
        condition
        for condition in stock.conditions
        if not state.is_done(f"{stock.key}:{condition.id}")
    ]
    if not active_conditions:
        print(f"Skipping completed stock conditions: {stock.name} ({stock.ticker})")
        return []

    try:
        quote = client.get_current_price(stock)
    except TemporaryKISDataUnavailable as exc:
        print(f"{exc}; skipping stock for this run")
        return []
    daily_closes: list[float] | None = None
    daily_prices_unavailable = False
    now = datetime.now(timezone.utc)
    alerts: list[Alert] = []

    for condition in active_conditions:
        if condition.type == "sma_cross" and daily_prices_unavailable:
            continue
        if condition.type == "sma_cross" and daily_closes is None:
            try:
                daily_closes = client.get_daily_closes(stock)
            except TemporaryKISDataUnavailable as exc:
                print(f"{exc}; skipping SMA conditions for this run")
                daily_prices_unavailable = True
                continue
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
