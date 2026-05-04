from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from kis_alert_bot.market_hours import is_market_open
from kis_alert_bot.models import Stock


class MarketHoursTests(unittest.TestCase):
    def test_kr_regular_session(self) -> None:
        stock = Stock(name="Samsung", ticker="005930", market="KR")
        now = datetime(2026, 5, 4, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        self.assertTrue(is_market_open(stock, now))

    def test_us_extended_session(self) -> None:
        stock = Stock(name="Apple", ticker="AAPL", market="US", exchange="NASD")
        now = datetime(2026, 5, 4, 4, 30, tzinfo=ZoneInfo("America/New_York"))
        self.assertTrue(is_market_open(stock, now))

    def test_weekend_closed(self) -> None:
        stock = Stock(name="Apple", ticker="AAPL", market="US", exchange="NASD")
        now = datetime(2026, 5, 3, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        self.assertFalse(is_market_open(stock, now))


if __name__ == "__main__":
    unittest.main()
