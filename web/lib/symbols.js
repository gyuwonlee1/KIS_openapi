import fs from "node:fs";
import path from "node:path";

const DATA_DIR = path.join(process.cwd(), "data", "symbols");
const MAX_RESULTS = 30;

let cache = null;

export function loadSymbolMaster() {
  if (cache) {
    return cache;
  }
  const kr = readSymbols("kr.json");
  const us = readSymbols("us.json");
  cache = { KR: kr, US: us, all: [...kr, ...us] };
  return cache;
}

export function searchSymbols(query, market) {
  const q = normalizeSearchText(query);
  if (q.length < 1) {
    return [];
  }

  const symbols = loadSymbolsForMarket(market);
  return symbols
    .map((symbol) => ({ symbol, score: scoreSymbol(symbol, q) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score || left.symbol.name.localeCompare(right.symbol.name))
    .slice(0, MAX_RESULTS)
    .map((entry) => entry.symbol);
}

export function findSymbol(stock) {
  if (!stock || typeof stock !== "object") {
    return null;
  }
  const market = String(stock.market || "").trim().toUpperCase();
  const ticker = String(stock.ticker || "").trim().toUpperCase();
  const exchange = normalizeExchange(stock.exchange || "");
  if (!ticker || !["KR", "US"].includes(market)) {
    return null;
  }

  const symbols = loadSymbolsForMarket(market);
  return (
    symbols.find((symbol) => {
      if (symbol.ticker !== ticker) {
        return false;
      }
      if (market !== "US") {
        return true;
      }
      return normalizeExchange(symbol.exchange) === exchange;
    }) || null
  );
}

export function validateSymbolsInPortfolio(portfolio) {
  const errors = [];
  if (!portfolio || !Array.isArray(portfolio.stocks)) {
    return errors;
  }
  portfolio.stocks.forEach((stock, stockIndex) => {
    if (!findSymbol(stock)) {
      const name = stock?.name || stock?.ticker || stockIndex + 1;
      errors.push(`stocks[${stockIndex}] ${name} is not in the verified symbol master`);
    }
  });
  return errors;
}

function loadSymbolsForMarket(market) {
  const normalized = String(market || "").trim().toUpperCase();
  const master = loadSymbolMaster();
  if (normalized === "KR") {
    return master.KR;
  }
  if (normalized === "US") {
    return master.US;
  }
  return master.all;
}

function readSymbols(fileName) {
  const filePath = path.join(DATA_DIR, fileName);
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw);
}

function scoreSymbol(symbol, q) {
  const ticker = normalizeSearchText(symbol.ticker);
  const name = normalizeSearchText(symbol.name);
  const exchange = normalizeSearchText(symbol.exchange || "");

  if (ticker === q) {
    return 1000;
  }
  if (name === q) {
    return 900;
  }
  if (ticker.startsWith(q)) {
    return 800;
  }
  if (name.startsWith(q)) {
    return 700;
  }
  if (ticker.includes(q)) {
    return 500;
  }
  if (name.includes(q)) {
    return 400;
  }
  if (exchange.includes(q)) {
    return 100;
  }
  return 0;
}

function normalizeSearchText(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, " ");
}

function normalizeExchange(exchange) {
  const value = String(exchange || "").trim().toUpperCase();
  if (value === "NASDAQ" || value === "NAS") {
    return "NASD";
  }
  if (value === "NYS") {
    return "NYSE";
  }
  if (value === "AMS") {
    return "AMEX";
  }
  return value;
}
