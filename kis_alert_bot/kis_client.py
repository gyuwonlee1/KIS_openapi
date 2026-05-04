from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from kis_alert_bot.models import PriceQuote, Stock


EXCHANGE_ALIASES = {
    "NASD": "NAS",
    "NASDAQ": "NAS",
    "NAS": "NAS",
    "NYSE": "NYS",
    "NYS": "NYS",
    "AMEX": "AMS",
    "AMS": "AMS",
}


class KISClient:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        base_url: str,
        min_interval_seconds: float = 0.2,
        overseas_interval_seconds: float = 1.0,
        timeout_seconds: float = 10.0,
        session: Any | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.min_interval_seconds = max(min_interval_seconds, 0.2)
        self.overseas_interval_seconds = max(overseas_interval_seconds, self.min_interval_seconds)
        self.timeout_seconds = timeout_seconds
        if session is None:
            import requests

            session = requests.Session()
        self.session = session
        self.access_token: str | None = None
        self._last_call_at = 0.0

    def issue_token(self) -> str:
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        data = self._request(
            "POST",
            "/oauth2/tokenP",
            headers={"content-type": "application/json"},
            json=payload,
        )
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"KIS token response did not include access_token: {data}")
        self.access_token = str(token)
        return self.access_token

    def get_current_price(self, stock: Stock) -> PriceQuote:
        self._ensure_token()
        if stock.market == "KR":
            data = self._get_domestic_current_price(stock)
            price = _read_float(data.get("output", {}), ["stck_prpr"])
        elif stock.market == "US":
            data = self._get_overseas_current_price(stock)
            price = _read_float(data.get("output", {}), ["last"])
        else:
            raise ValueError(f"unsupported market: {stock.market}")
        return PriceQuote(stock=stock, price=price, raw=data)

    def get_daily_closes(self, stock: Stock) -> list[float]:
        self._ensure_token()
        if stock.market == "KR":
            data = self._get_domestic_daily_prices(stock)
            rows = data.get("output2") or data.get("output") or []
            closes = [_read_float(row, ["stck_clpr"]) for row in rows if isinstance(row, dict)]
        elif stock.market == "US":
            data = self._get_overseas_daily_prices(stock)
            rows = data.get("output2") or []
            closes = [_read_float(row, ["clos"]) for row in rows if isinstance(row, dict)]
        else:
            raise ValueError(f"unsupported market: {stock.market}")

        closes = [value for value in closes if value > 0]
        closes.reverse()
        return closes

    def _get_domestic_current_price(self, stock: Stock) -> dict[str, Any]:
        return self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=self._headers("FHKST01010100"),
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock.ticker,
            },
        )

    def _get_overseas_current_price(self, stock: Stock) -> dict[str, Any]:
        return self._request(
            "GET",
            "/uapi/overseas-price/v1/quotations/price",
            headers=self._headers("HHDFS00000300"),
            params={
                "AUTH": "",
                "EXCD": normalize_exchange(stock.exchange),
                "SYMB": stock.ticker,
            },
            min_interval=self.overseas_interval_seconds,
        )

    def _get_domestic_daily_prices(self, stock: Stock) -> dict[str, Any]:
        end_date = datetime.now().strftime("%Y%m%d")
        return self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            headers=self._headers("FHKST03010100"),
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock.ticker,
                "FID_INPUT_DATE_1": "19000101",
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )

    def _get_overseas_daily_prices(self, stock: Stock) -> dict[str, Any]:
        end_date = datetime.now().strftime("%Y%m%d")
        return self._request(
            "GET",
            "/uapi/overseas-price/v1/quotations/dailyprice",
            headers=self._headers("HHDFS76240000"),
            params={
                "AUTH": "",
                "EXCD": normalize_exchange(stock.exchange),
                "SYMB": stock.ticker,
                "GUBN": "0",
                "BYMD": end_date,
                "MODP": "1",
            },
            min_interval=self.overseas_interval_seconds,
        )

    def _headers(self, tr_id: str) -> dict[str, str]:
        token = self._ensure_token()
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _ensure_token(self) -> str:
        if not self.access_token:
            return self.issue_token()
        return self.access_token

    def _request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        min_interval: float | None = None,
    ) -> dict[str, Any]:
        self._throttle(min_interval or self.min_interval_seconds)
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            params=params,
            json=json,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"KIS returned non-object response for {path}")
        rt_cd = data.get("rt_cd")
        if rt_cd is not None and str(rt_cd) != "0":
            message = data.get("msg1") or data.get("msg_cd") or data
            raise RuntimeError(f"KIS API error for {path}: {message}")
        return data

    def _throttle(self, min_interval: float) -> None:
        elapsed = time.monotonic() - self._last_call_at
        wait_seconds = min_interval - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._last_call_at = time.monotonic()


def normalize_exchange(exchange: str | None) -> str:
    if not exchange:
        raise ValueError("US stock requires exchange")
    normalized = EXCHANGE_ALIASES.get(exchange.upper())
    if not normalized:
        raise ValueError(f"unsupported US exchange: {exchange}")
    return normalized


def _read_float(payload: dict[str, Any], keys: list[str]) -> float:
    for key in keys:
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            continue
    raise RuntimeError(f"could not read numeric field from keys {keys}: {payload}")
