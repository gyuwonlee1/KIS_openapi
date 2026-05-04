from __future__ import annotations

import unittest

from kis_alert_bot.kis_client import KISClient, normalize_exchange
from kis_alert_bot.models import Stock


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.requests: list[dict] = []

    def request(self, method: str, url: str, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return FakeResponse(self.payloads.pop(0))


class KISClientTests(unittest.TestCase):
    def test_parses_domestic_current_price(self) -> None:
        session = FakeSession(
            [
                {"access_token": "token"},
                {"rt_cd": "0", "output": {"stck_prpr": "80000"}},
            ]
        )
        client = KISClient("key", "secret", "https://example.test", session=session)
        quote = client.get_current_price(Stock(name="Samsung", ticker="005930", market="KR"))
        self.assertEqual(quote.price, 80000)
        self.assertEqual(session.requests[1]["params"]["FID_INPUT_ISCD"], "005930")

    def test_parses_overseas_daily_closes(self) -> None:
        session = FakeSession(
            [
                {"access_token": "token"},
                {"rt_cd": "0", "output2": [{"clos": "101.5"}, {"clos": "100.5"}]},
            ]
        )
        client = KISClient(
            "key",
            "secret",
            "https://example.test",
            min_interval_seconds=0.2,
            overseas_interval_seconds=0.2,
            session=session,
        )
        closes = client.get_daily_closes(
            Stock(name="Apple", ticker="AAPL", market="US", exchange="NASD")
        )
        self.assertEqual(closes, [100.5, 101.5])

    def test_normalize_exchange_aliases(self) -> None:
        self.assertEqual(normalize_exchange("NASD"), "NAS")
        self.assertEqual(normalize_exchange("NYSE"), "NYS")
        self.assertEqual(normalize_exchange("AMEX"), "AMS")


if __name__ == "__main__":
    unittest.main()
