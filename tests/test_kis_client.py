from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from kis_alert_bot.kis_client import (
    KISClient,
    KST,
    NEW_YORK,
    TemporaryKISDataUnavailable,
    _daily_date_range,
    _token_expires_at,
    normalize_exchange,
)
from kis_alert_bot.models import Stock


def temporary_path(name: str) -> Path:
    base = Path(".tmp-tests")
    base.mkdir(exist_ok=True)
    return base / f"{name}-{uuid.uuid4().hex}.json"


class FakeHTTPError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.response = type("Response", (), {"status_code": status_code})()


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise FakeHTTPError(self.status_code)

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[dict | FakeResponse]) -> None:
        self.responses = [
            response if isinstance(response, FakeResponse) else FakeResponse(response)
            for response in responses
        ]
        self.requests: list[dict] = []

    def request(self, method: str, url: str, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


class KISClientTests(unittest.TestCase):
    def test_parses_domestic_current_price(self) -> None:
        session = FakeSession(
            [
                {"access_token": "token"},
                {"rt_cd": "0", "output": {"stck_prpr": "80000"}},
            ]
        )
        client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=None)
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
            token_cache_path=None,
        )
        closes = client.get_daily_closes(
            Stock(name="Apple", ticker="AAPL", market="US", exchange="NASD")
        )
        self.assertEqual(closes, [100.5, 101.5])

    def test_domestic_daily_request_uses_recent_history_window(self) -> None:
        session = FakeSession(
            [
                {"access_token": "token"},
                {"rt_cd": "0", "output2": [{"stck_clpr": "80000"}]},
            ]
        )
        client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=None)

        closes = client.get_daily_closes(Stock(name="Samsung", ticker="005930", market="KR"))

        params = session.requests[1]["params"]
        self.assertEqual(closes, [80000])
        self.assertNotEqual(params["FID_INPUT_DATE_1"], "19000101")
        self.assertEqual(len(params["FID_INPUT_DATE_1"]), 8)
        self.assertEqual(len(params["FID_INPUT_DATE_2"]), 8)
        self.assertLess(params["FID_INPUT_DATE_1"], params["FID_INPUT_DATE_2"])

    def test_daily_date_ranges_use_market_timezones(self) -> None:
        now = datetime(2026, 5, 5, 15, 30, tzinfo=timezone.utc)

        _kr_start, kr_end = _daily_date_range(KST, now=now, lookback_days=1)
        _us_start, us_end = _daily_date_range(NEW_YORK, now=now, lookback_days=1)

        self.assertEqual(kr_end, "20260506")
        self.assertEqual(us_end, "20260505")

    def test_daily_server_error_is_temporary_data_unavailable(self) -> None:
        # 500 is retried MAX_RETRIES times before surfacing as unavailable.
        session = FakeSession(
            [
                {"access_token": "token"},
                FakeResponse({}, status_code=500),
                FakeResponse({}, status_code=500),
                FakeResponse({}, status_code=500),
            ]
        )
        client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=None)

        with patch("kis_alert_bot.kis_client.time.sleep"):
            with self.assertRaises(TemporaryKISDataUnavailable):
                client.get_daily_closes(Stock(name="Samsung", ticker="005930", market="KR"))

    def test_retryable_error_retries_then_succeeds(self) -> None:
        session = FakeSession(
            [
                {"access_token": "token"},
                FakeResponse({}, status_code=503),
                {"rt_cd": "0", "output": {"stck_prpr": "80000"}},
            ]
        )
        client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=None)

        with patch("kis_alert_bot.kis_client.time.sleep"):
            quote = client.get_current_price(Stock(name="Samsung", ticker="005930", market="KR"))

        self.assertEqual(quote.price, 80000)

    def test_current_price_transient_becomes_temporary_unavailable(self) -> None:
        session = FakeSession(
            [
                {"access_token": "token"},
                FakeResponse({}, status_code=500),
                FakeResponse({}, status_code=500),
                FakeResponse({}, status_code=500),
            ]
        )
        client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=None)

        with patch("kis_alert_bot.kis_client.time.sleep"):
            with self.assertRaises(TemporaryKISDataUnavailable):
                client.get_current_price(Stock(name="Samsung", ticker="005930", market="KR"))

    def test_issues_token_and_saves_cache_when_cache_is_missing(self) -> None:
        path = temporary_path("token")
        session = FakeSession(
            [
                {"access_token": "new-token", "expires_in": 86400},
                {"rt_cd": "0", "output": {"stck_prpr": "80000"}},
            ]
        )
        try:
            client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=path)
            client.get_current_price(Stock(name="Samsung", ticker="005930", market="KR"))
            cache = json.loads(path.read_text(encoding="utf-8"))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(session.requests[0]["url"], "https://example.test/oauth2/tokenP")
        self.assertEqual(cache["access_token"], "new-token")
        self.assertIn("expires_at", cache)

    def test_reuses_valid_cached_token_without_issuing_token(self) -> None:
        path = temporary_path("token")
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        path.write_text(
            json.dumps(
                {
                    "access_token": "cached-token",
                    "issued_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "app_key_hash": _app_key_hash_for_test("key"),
                    "base_url": "https://example.test",
                }
            ),
            encoding="utf-8",
        )
        session = FakeSession([{"rt_cd": "0", "output": {"stck_prpr": "80000"}}])
        try:
            client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=path)
            client.get_current_price(Stock(name="Samsung", ticker="005930", market="KR"))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(len(session.requests), 1)
        self.assertEqual(session.requests[0]["headers"]["authorization"], "Bearer cached-token")

    def test_expired_cached_token_is_reissued(self) -> None:
        path = temporary_path("token")
        path.write_text(
            json.dumps(
                {
                    "access_token": "expired-token",
                    "issued_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                    "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                    "app_key_hash": _app_key_hash_for_test("key"),
                    "base_url": "https://example.test",
                }
            ),
            encoding="utf-8",
        )
        session = FakeSession(
            [
                {"access_token": "new-token"},
                {"rt_cd": "0", "output": {"stck_prpr": "80000"}},
            ]
        )
        try:
            client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=path)
            client.get_current_price(Stock(name="Samsung", ticker="005930", market="KR"))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(session.requests[0]["url"], "https://example.test/oauth2/tokenP")

    def test_cache_with_different_app_key_is_not_reused(self) -> None:
        path = temporary_path("token")
        path.write_text(
            json.dumps(
                {
                    "access_token": "other-token",
                    "issued_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    "app_key_hash": _app_key_hash_for_test("other-key"),
                    "base_url": "https://example.test",
                }
            ),
            encoding="utf-8",
        )
        session = FakeSession(
            [
                {"access_token": "new-token"},
                {"rt_cd": "0", "output": {"stck_prpr": "80000"}},
            ]
        )
        try:
            client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=path)
            client.get_current_price(Stock(name="Samsung", ticker="005930", market="KR"))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(session.requests[0]["url"], "https://example.test/oauth2/tokenP")

    def test_kis_naive_token_expiry_is_treated_as_korean_time(self) -> None:
        issued_at = datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc)
        expires_at = _token_expires_at(
            {"access_token_token_expired": "2026-05-06 09:00:00"},
            issued_at,
        )

        self.assertEqual(expires_at, datetime(2026, 5, 6, 0, 0, tzinfo=timezone.utc))

    def test_auth_error_invalidates_cache_and_retries_once(self) -> None:
        path = temporary_path("token")
        path.write_text(
            json.dumps(
                {
                    "access_token": "cached-token",
                    "issued_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    "app_key_hash": _app_key_hash_for_test("key"),
                    "base_url": "https://example.test",
                }
            ),
            encoding="utf-8",
        )
        session = FakeSession(
            [
                FakeResponse({}, status_code=401),
                {"access_token": "new-token"},
                {"rt_cd": "0", "output": {"stck_prpr": "80000"}},
            ]
        )
        try:
            client = KISClient("key", "secret", "https://example.test", session=session, token_cache_path=path)
            quote = client.get_current_price(Stock(name="Samsung", ticker="005930", market="KR"))
            cache = json.loads(path.read_text(encoding="utf-8"))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(quote.price, 80000)
        self.assertEqual(session.requests[1]["url"], "https://example.test/oauth2/tokenP")
        self.assertEqual(session.requests[2]["headers"]["authorization"], "Bearer new-token")
        self.assertEqual(cache["access_token"], "new-token")

    def test_normalize_exchange_aliases(self) -> None:
        self.assertEqual(normalize_exchange("NASD"), "NAS")
        self.assertEqual(normalize_exchange("NYSE"), "NYS")
        self.assertEqual(normalize_exchange("AMEX"), "AMS")


def _app_key_hash_for_test(app_key: str) -> str:
    import hashlib

    return hashlib.sha256(app_key.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
