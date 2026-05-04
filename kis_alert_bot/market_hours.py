from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from kis_alert_bot.models import Stock


KST = ZoneInfo("Asia/Seoul")
NEW_YORK = ZoneInfo("America/New_York")


def is_market_open(stock: Stock, now: datetime | None = None) -> bool:
    now = now or datetime.now(tz=ZoneInfo("UTC"))
    if stock.market == "KR":
        local_now = now.astimezone(KST)
        return _is_weekday(local_now) and time(9, 0) <= local_now.time() <= time(15, 30)
    if stock.market == "US":
        local_now = now.astimezone(NEW_YORK)
        return _is_weekday(local_now) and time(4, 0) <= local_now.time() <= time(20, 0)
    return False


def _is_weekday(value: datetime) -> bool:
    return value.weekday() < 5
