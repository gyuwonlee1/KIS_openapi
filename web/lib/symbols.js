import fs from "node:fs";
import path from "node:path";

const DATA_DIR = path.join(process.cwd(), "data", "symbols");
const MAX_RESULTS = 30;
const COMPANY_SUFFIX_PATTERN =
  /\b(INC|INCORPORATED|CORP|CORPORATION|COMPANY|CO|LTD|LIMITED|PLC|SA|NV|AG|HOLDINGS?|GROUP|CLASS [A-Z]|COMMON STOCK|ORDINARY SHARES?)\b/g;

let cache = null;

export function loadSymbolMaster() {
  if (cache) {
    return cache;
  }
  const kr = readSymbols("kr.json");
  const us = readSymbols("us.json");
  const all = [...kr, ...us];
  const aliasByKey = buildAliasMap(all, readAliases());
  cache = { KR: kr, US: us, all, aliasByKey };
  return cache;
}

export function searchSymbols(query, market) {
  return searchSymbolMatches(query, market).map((entry) => entry.symbol);
}

export function searchSymbolMatches(query, market, limit = MAX_RESULTS) {
  const q = normalizeSearchText(query);
  const qCompact = normalizeCompact(query);
  if (q.length < 1 || qCompact.length < 1) {
    return [];
  }

  const master = loadSymbolMaster();
  const symbols = loadSymbolsForMarket(market);
  return symbols
    .map((symbol) => ({
      symbol,
      score: scoreSymbol(symbol, q, qCompact, master.aliasByKey.get(stockKey(symbol)) || []),
    }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score || left.symbol.name.localeCompare(right.symbol.name))
    .slice(0, limit);
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
      return !exchange || normalizeExchange(symbol.exchange) === exchange;
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

function readAliases() {
  const filePath = path.join(DATA_DIR, "aliases.json");
  if (!fs.existsSync(filePath)) {
    return [];
  }
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function buildAliasMap(symbols, aliases) {
  const symbolByKey = new Map(symbols.map((symbol) => [stockKey(symbol), symbol]));
  const aliasByKey = new Map();

  aliases.forEach((entry) => {
    const market = String(entry.market || "").trim().toUpperCase();
    const ticker = String(entry.ticker || "").trim().toUpperCase();
    const exchange = normalizeExchange(entry.exchange || "");
    const candidates = symbols.filter((symbol) => {
      if (symbol.market !== market || symbol.ticker !== ticker) {
        return false;
      }
      return market !== "US" || !exchange || normalizeExchange(symbol.exchange) === exchange;
    });
    const symbol = candidates[0] || symbolByKey.get(`${market}:${exchange}:${ticker}`) || symbolByKey.get(`${market}:${ticker}`);
    if (!symbol) {
      return;
    }
    const key = stockKey(symbol);
    const next = aliasByKey.get(key) || [];
    aliasByKey.set(key, [...next, ...(Array.isArray(entry.aliases) ? entry.aliases : [])]);
  });

  return aliasByKey;
}

function scoreSymbol(symbol, q, qCompact, aliases) {
  const ticker = normalizeSearchText(symbol.ticker);
  const tickerCompact = normalizeCompact(symbol.ticker);
  const name = normalizeSearchText(symbol.name);
  const nameCompact = normalizeCompact(symbol.name);
  const companyName = normalizeCompanyName(symbol.name);
  const exchange = normalizeSearchText(symbol.exchange || "");
  const aliasScores = aliases.map((alias) => scoreText(alias, q, qCompact, 1150, 900, 650));

  return Math.max(
    scoreText(ticker, q, qCompact, 1200, 950, 700),
    scoreText(tickerCompact, q, qCompact, 1200, 950, 700),
    scoreText(name, q, qCompact, 1000, 800, 550),
    scoreText(nameCompact, q, qCompact, 1000, 800, 550),
    scoreText(companyName, q, qCompact, 980, 780, 520),
    scoreText(exchange, q, qCompact, 100, 80, 60),
    ...aliasScores,
  );
}

function scoreText(value, q, qCompact, exactScore, startsScore, includesScore) {
  const text = normalizeSearchText(value);
  const compact = normalizeCompact(value);
  if (!text || !compact) {
    return 0;
  }
  if (text === q || compact === qCompact) {
    return exactScore;
  }
  if (text.startsWith(q) || compact.startsWith(qCompact)) {
    return startsScore;
  }
  if (text.includes(q) || compact.includes(qCompact)) {
    return includesScore;
  }
  return 0;
}

function normalizeSearchText(value) {
  return String(value || "")
    .normalize("NFKC")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, " ");
}

function normalizeCompact(value) {
  return String(value || "")
    .normalize("NFKC")
    .toUpperCase()
    .replace(/[^\p{L}\p{N}]+/gu, "");
}

function normalizeCompanyName(value) {
  return normalizeSearchText(value).replace(COMPANY_SUFFIX_PATTERN, "").replace(/\s+/g, " ").trim();
}

function stockKey(stock) {
  const market = String(stock.market || "").trim().toUpperCase();
  const ticker = String(stock.ticker || "").trim().toUpperCase();
  const exchange = normalizeExchange(stock.exchange || "");
  if (market === "US" && exchange) {
    return `${market}:${exchange}:${ticker}`;
  }
  return `${market}:${ticker}`;
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
