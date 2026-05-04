"""Build web stock-symbol search data from official public master files."""

from __future__ import annotations

import csv
import io
import json
import re
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web" / "data" / "symbols"

KR_MASTERS = [
    ("KOSPI", "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip", "kospi_code.mst", 228),
    ("KOSDAQ", "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip", "kosdaq_code.mst", 222),
    ("KONEX", "https://new.real.download.dws.co.kr/common/master/konex_code.mst.zip", "konex_code.mst", 228),
]

US_NASDAQ = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
US_OTHER = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    kr_symbols = build_kr_symbols()
    us_symbols = build_us_symbols()
    write_json(OUT_DIR / "kr.json", kr_symbols)
    write_json(OUT_DIR / "us.json", us_symbols)
    print(f"Wrote {len(kr_symbols)} KR symbols and {len(us_symbols)} US symbols")


def build_kr_symbols() -> list[dict[str, str]]:
    symbols: list[dict[str, str]] = []
    seen: set[str] = set()
    for exchange, url, member_name, trailer_size in KR_MASTERS:
        try:
            rows = read_kr_master(url, member_name, trailer_size)
        except Exception as exc:  # pragma: no cover - network/source fallback
            print(f"Skipping {exchange}: {exc}")
            continue
        for ticker, name in rows:
            if not re.fullmatch(r"\d{6}", ticker) or not name or ticker in seen:
                continue
            seen.add(ticker)
            symbols.append(
                {
                    "market": "KR",
                    "exchange": exchange,
                    "ticker": ticker,
                    "name": name,
                    "source": "KIS stocks_info",
                }
            )
    return sorted(symbols, key=lambda item: (item["ticker"], item["name"]))


def read_kr_master(url: str, member_name: str, trailer_size: int) -> list[tuple[str, str]]:
    raw_zip = download(url)
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        with archive.open(member_name) as handle:
            text = handle.read().decode("cp949", errors="replace")

    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line:
            continue
        head = line[: len(line) - trailer_size]
        ticker = head[:9].strip()
        name = head[21:].strip()
        rows.append((ticker, name))
    return rows


def build_us_symbols() -> list[dict[str, str]]:
    symbols: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for row in read_pipe_rows(US_NASDAQ):
        if row.get("Test Issue") == "Y" or row.get("Symbol") == "File Creation Time":
            continue
        ticker = clean_us_symbol(row.get("Symbol", ""))
        name = clean_us_name(row.get("Security Name", ""))
        add_us_symbol(symbols, seen, ticker, name, "NASD")

    for row in read_pipe_rows(US_OTHER):
        if row.get("Test Issue") == "Y" or row.get("ACT Symbol") == "File Creation Time":
            continue
        exchange = map_otherlisted_exchange(row.get("Exchange", ""))
        if not exchange:
            continue
        ticker = clean_us_symbol(row.get("ACT Symbol", ""))
        name = clean_us_name(row.get("Security Name", ""))
        add_us_symbol(symbols, seen, ticker, name, exchange)

    return sorted(symbols, key=lambda item: (item["ticker"], item["exchange"], item["name"]))


def read_pipe_rows(url: str) -> list[dict[str, str]]:
    text = download(url).decode("utf8", errors="replace")
    return list(csv.DictReader(io.StringIO(text), delimiter="|"))


def add_us_symbol(
    symbols: list[dict[str, str]],
    seen: set[tuple[str, str]],
    ticker: str,
    name: str,
    exchange: str,
) -> None:
    if not ticker or not name:
        return
    key = (exchange, ticker)
    if key in seen:
        return
    seen.add(key)
    symbols.append(
        {
            "market": "US",
            "exchange": exchange,
            "ticker": ticker,
            "name": name,
            "source": "Nasdaq Trader Symbol Directory",
        }
    )


def map_otherlisted_exchange(exchange: str) -> str | None:
    value = exchange.strip().upper()
    if value == "N":
        return "NYSE"
    if value in {"A", "M"}:
        return "AMEX"
    return None


def clean_us_symbol(value: str) -> str:
    return value.strip().upper().replace(".", "-")


def clean_us_name(value: str) -> str:
    name = re.sub(r"\s+", " ", value).strip()
    name = re.sub(r" - (Common Stock|Class [A-Z] Common Stock|Ordinary Shares).*$", "", name)
    name = re.sub(r" (Class [A-Z] )?Common Stock$", "", name)
    name = re.sub(r" Ordinary Shares$", "", name)
    name = re.sub(r" American Depositary Shares$", "", name)
    return name


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "kis-alert-bot-symbol-updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def write_json(path: Path, data: list[dict[str, str]]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf8", delete=False, dir=path.parent) as temp:
        json.dump(data, temp, ensure_ascii=False, indent=2)
        temp.write("\n")
        temp_path = Path(temp.name)
    temp_path.replace(path)


if __name__ == "__main__":
    main()
