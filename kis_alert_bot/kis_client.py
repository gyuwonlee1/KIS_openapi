from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
DEFAULT_TOKEN_TTL = timedelta(hours=23)
# 760 calendar days ≈ 525 trading days, enough for the max SMA window (480 days)
# plus the previous-day value needed for cross detection and a safety buffer.
DAILY_HISTORY_LOOKBACK_DAYS = 760
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 0.5
KST = ZoneInfo("Asia/Seoul")
NEW_YORK = ZoneInfo("America/New_York")
TOKEN_PATH = "/oauth2/tokenP"


class KISAPIError(RuntimeError):
    def __init__(self, path: str, data: dict[str, Any]) -> None:
        self.path = path
        self.data = data
        message = data.get("msg1") or data.get("msg_cd") or data
        super().__init__(f"KIS API error for {path}: {message}")


class TemporaryKISDataUnavailable(RuntimeError):
    pass


class KISClient:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        base_url: str,
        min_interval_seconds: float = 0.2,
        overseas_interval_seconds: float = 1.0,
        timeout_seconds: float = 10.0,
        token_cache_path: str | Path | None = ".cache/kis-alerts/kis_token.json",
        session: Any | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.min_interval_seconds = max(min_interval_seconds, 0.2)
        self.overseas_interval_seconds = max(overseas_interval_seconds, self.min_interval_seconds)
        self.timeout_seconds = timeout_seconds
        self.token_cache_path = Path(token_cache_path) if token_cache_path else None
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
            TOKEN_PATH,
            headers={"content-type": "application/json"},
            json=payload,
            retry_auth=False,
        )
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"KIS token response did not include access_token: {data}")
        self.access_token = str(token)
        self._save_token_cache(data)
        return self.access_token

    def get_current_price(self, stock: Stock) -> PriceQuote:
        self._ensure_token()
        try:
            if stock.market == "KR":
                data = self._get_domestic_current_price(stock)
                price = _read_float(data.get("output", {}), ["stck_prpr"])
            elif stock.market == "US":
                data = self._get_overseas_current_price(stock)
                price = _read_float(data.get("output", {}), ["last"])
            else:
                raise ValueError(f"unsupported market: {stock.market}")
        except Exception as exc:
            if _is_retryable(exc):
                raise TemporaryKISDataUnavailable(
                    f"temporary price unavailable for {stock.name} ({stock.ticker})"
                ) from exc
            raise
        return PriceQuote(stock=stock, price=price, raw=data)

    def get_daily_closes(self, stock: Stock) -> list[float]:
        self._ensure_token()
        try:
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
        except Exception as exc:
            if _is_retryable(exc):
                raise TemporaryKISDataUnavailable(f"temporary daily price unavailable for {stock.name} ({stock.ticker})") from exc
            raise

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
        start_date, end_date = _daily_date_range(KST)
        return self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            headers=self._headers("FHKST03010100"),
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock.ticker,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )

    def _get_overseas_daily_prices(self, stock: Stock) -> dict[str, Any]:
        _start_date, end_date = _daily_date_range(NEW_YORK)
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
        if self.access_token:
            return self.access_token
        cached_token = self._load_token_cache()
        if cached_token:
            self.access_token = cached_token
            return self.access_token
        return self.issue_token()

    def _request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        min_interval: float | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        attempt = 0
        auth_retried = False
        while True:
            try:
                return self._request_once(method, path, headers, params, json, min_interval)
            except Exception as exc:
                # Auth error: refresh the token once, then retry.
                if (
                    retry_auth
                    and not auth_retried
                    and path != TOKEN_PATH
                    and _is_auth_error(exc)
                ):
                    auth_retried = True
                    self._invalidate_token_cache()
                    self.access_token = None
                    token = self.issue_token()
                    headers = _with_bearer(headers, token)
                    continue
                # Transient error (429 / 5xx / timeout): back off and retry.
                if _is_retryable(exc) and attempt < MAX_RETRIES:
                    attempt += 1
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                raise

    def _request_once(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
        min_interval: float | None,
    ) -> dict[str, Any]:
        self._throttle(min_interval or self.min_interval_seconds)
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"KIS returned non-object response for {path}")
        rt_cd = data.get("rt_cd")
        if rt_cd is not None and str(rt_cd) != "0":
            raise KISAPIError(path, data)
        return data

    def _load_token_cache(self) -> str | None:
        if not self.token_cache_path or not self.token_cache_path.exists():
            return None
        try:
            with self.token_cache_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        token = data.get("access_token")
        if not isinstance(token, str) or not token.strip():
            return None
        if data.get("app_key_hash") != _app_key_hash(self.app_key):
            return None
        if data.get("base_url") != self.base_url:
            return None
        expires_at = _parse_datetime(data.get("expires_at"))
        issued_at = _parse_datetime(data.get("issued_at"))
        now = datetime.now(timezone.utc)
        if expires_at is not None:
            return token if expires_at > now else None
        if issued_at is not None and issued_at + DEFAULT_TOKEN_TTL > now:
            return token
        return None

    def _save_token_cache(self, token_response: dict[str, Any]) -> None:
        if not self.token_cache_path or not self.access_token:
            return
        issued_at = datetime.now(timezone.utc)
        expires_at = _token_expires_at(token_response, issued_at)
        payload = {
            "access_token": self.access_token,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "app_key_hash": _app_key_hash(self.app_key),
            "base_url": self.base_url,
        }
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.token_cache_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")

    def _invalidate_token_cache(self) -> None:
        if self.token_cache_path:
            self.token_cache_path.unlink(missing_ok=True)

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


def _daily_date_range(
    market_timezone: ZoneInfo,
    now: datetime | None = None,
    lookback_days: int = DAILY_HISTORY_LOOKBACK_DAYS,
) -> tuple[str, str]:
    local_now = (now or datetime.now(timezone.utc)).astimezone(market_timezone)
    start_date = local_now.date() - timedelta(days=lookback_days)
    return start_date.strftime("%Y%m%d"), local_now.strftime("%Y%m%d")


def _app_key_hash(app_key: str) -> str:
    return hashlib.sha256(app_key.encode("utf-8")).hexdigest()


def _token_expires_at(token_response: dict[str, Any], issued_at: datetime) -> datetime:
    for key in ("expires_at", "access_token_token_expired", "token_expired"):
        parsed = _parse_datetime(token_response.get(key), default_timezone=KST)
        if parsed:
            return parsed
    expires_in = token_response.get("expires_in")
    try:
        if expires_in is not None:
            seconds = int(expires_in)
            return issued_at + timedelta(seconds=max(0, seconds - 600))
    except (TypeError, ValueError):
        pass
    return issued_at + DEFAULT_TOKEN_TTL


def _parse_datetime(value: Any, default_timezone: timezone | ZoneInfo = timezone.utc) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=default_timezone)
    return parsed.astimezone(timezone.utc)


def _is_auth_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code in {401, 403}:
        return True
    if isinstance(exc, KISAPIError):
        data_text = " ".join(str(value) for value in exc.data.values()).lower()
        return any(
            marker in data_text
            for marker in (
                "token",
                "authorization",
                "unauthorized",
                "auth",
                "인증",
                "토큰",
                "기간",
                "만료",
            )
        )
    return False


def _is_server_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return isinstance(status_code, int) and 500 <= status_code < 600


def _is_retryable(exc: Exception) -> bool:
    """Transient failures worth retrying: HTTP 429/5xx and network timeouts."""
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and (status_code == 429 or 500 <= status_code < 600):
        return True
    # requests.exceptions.Timeout / ConnectionError (matched by name to avoid a
    # hard requests import and to keep the client testable with fake sessions).
    return type(exc).__name__ in {
        "Timeout",
        "ConnectTimeout",
        "ReadTimeout",
        "ConnectionError",
    }


def _with_bearer(headers: dict[str, str] | None, token: str) -> dict[str, str] | None:
    if not headers:
        return headers
    updated = dict(headers)
    for key in list(updated):
        if key.lower() == "authorization":
            updated[key] = f"Bearer {token}"
    return updated
