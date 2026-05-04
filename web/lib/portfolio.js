export const SUPPORTED_MARKETS = ["KR", "US"];
export const SUPPORTED_CONDITION_TYPES = ["price", "sma_cross"];
export const SUPPORTED_OPERATORS = [">=", "<="];
export const SUPPORTED_US_EXCHANGES = ["NASD", "NASDAQ", "NAS", "NYSE", "NYS", "AMEX", "AMS"];
export const SUPPORTED_SMA_WINDOWS = [20, 60, 240, 480];

export function emptyPortfolio() {
  return { stocks: [] };
}

export function createStockFromSymbol(symbol) {
  const market = String(symbol.market || "").trim().toUpperCase();
  const stock = {
    name: String(symbol.name || "").trim(),
    ticker: String(symbol.ticker || "").trim().toUpperCase(),
    market,
    enabled: true,
    conditions: [createCondition("price")],
  };
  if (market === "US") {
    stock.exchange = normalizeUsExchange(symbol.exchange || "NASD");
  }
  return stock;
}

export function createStock() {
  return {
    name: "",
    ticker: "",
    market: "KR",
    enabled: true,
    conditions: [createCondition("price")],
  };
}

export function createCondition(type = "price") {
  const id = newConditionId(type);
  if (type === "sma_cross") {
    return {
      id,
      type,
      operator: ">=",
      window: 20,
      delete_after_alert: true,
    };
  }
  return {
    id,
    type: "price",
    operator: ">=",
    target: 0,
    delete_after_alert: true,
  };
}

export function newConditionId(type = "condition") {
  const random =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${type}-${random}`;
}

export function conditionCore(condition) {
  if (!condition || typeof condition !== "object") {
    return "";
  }
  if (condition.type === "sma_cross") {
    return `${condition.type}:${condition.operator}:${Number.parseInt(condition.window, 10)}`;
  }
  return `${condition.type}:${condition.operator}:${Number(condition.target)}`;
}

export function validatePortfolio(portfolio) {
  const errors = [];
  if (!portfolio || typeof portfolio !== "object" || Array.isArray(portfolio)) {
    return ["portfolio root must be an object"];
  }
  if (!Array.isArray(portfolio.stocks)) {
    return ["portfolio.stocks must be an array"];
  }

  const keys = new Set();
  portfolio.stocks.forEach((stock, stockIndex) => {
    const prefix = `stocks[${stockIndex}]`;
    validateStock(stock, prefix, errors);
    if (!stock || typeof stock !== "object") {
      return;
    }
    const stockKey = stockKeyFor(stock);
    if (Array.isArray(stock.conditions)) {
      stock.conditions.forEach((condition, conditionIndex) => {
        const key = `${stockKey}:${condition?.id || conditionIndex}`;
        if (keys.has(key)) {
          errors.push(`${prefix}.conditions[${conditionIndex}].id is duplicated`);
        }
        keys.add(key);
      });
    }
  });
  return errors;
}

export function normalizePortfolio(portfolio) {
  return {
    stocks: portfolio.stocks.map((stock) => {
      const next = {
        name: String(stock.name || "").trim(),
        ticker: String(stock.ticker || "").trim().toUpperCase(),
        market: String(stock.market || "").trim().toUpperCase(),
        enabled: Boolean(stock.enabled),
        conditions: stock.conditions.map(normalizeCondition),
      };
      if (next.market === "US") {
        next.exchange = normalizeUsExchange(stock.exchange || "");
      }
      return next;
    }),
  };
}

function normalizeCondition(condition) {
  const type = String(condition.type || "").trim();
  const next = {
    id: String(condition.id || newConditionId(type || "condition")).trim(),
    type,
    operator: String(condition.operator || "").trim(),
    delete_after_alert: true,
  };
  if (condition.label) {
    next.label = String(condition.label).trim();
  }
  if (next.type === "price") {
    next.target = Number(condition.target);
  }
  if (next.type === "sma_cross") {
    next.window = Number.parseInt(condition.window, 10);
  }
  return next;
}

function validateStock(stock, prefix, errors) {
  if (!stock || typeof stock !== "object" || Array.isArray(stock)) {
    errors.push(`${prefix} must be an object`);
    return;
  }
  const name = String(stock.name || "").trim();
  const ticker = String(stock.ticker || "").trim().toUpperCase();
  const market = String(stock.market || "").trim().toUpperCase();

  if (!name) {
    errors.push(`${prefix}.name is required`);
  }
  if (!ticker) {
    errors.push(`${prefix}.ticker is required`);
  }
  if (market === "KR" && !/^\d{6}$/.test(ticker)) {
    errors.push(`${prefix}.ticker must be a 6 digit Korean stock code`);
  }

  if (!SUPPORTED_MARKETS.includes(market)) {
    errors.push(`${prefix}.market must be KR or US`);
  }
  const exchange = String(stock.exchange || "").trim().toUpperCase();
  if (market === "US" && !exchange) {
    errors.push(`${prefix}.exchange is required for US stocks`);
  }
  if (exchange && !SUPPORTED_US_EXCHANGES.includes(exchange)) {
    errors.push(`${prefix}.exchange is unsupported`);
  }
  if (!Array.isArray(stock.conditions) || stock.conditions.length === 0) {
    errors.push(`${prefix}.conditions must be a non-empty array`);
    return;
  }
  stock.conditions.forEach((condition, conditionIndex) => {
    validateCondition(condition, `${prefix}.conditions[${conditionIndex}]`, errors);
  });
}

function validateCondition(condition, prefix, errors) {
  if (!condition || typeof condition !== "object" || Array.isArray(condition)) {
    errors.push(`${prefix} must be an object`);
    return;
  }
  if (!String(condition.id || "").trim()) {
    errors.push(`${prefix}.id is required`);
  }
  if (!SUPPORTED_CONDITION_TYPES.includes(condition.type)) {
    errors.push(`${prefix}.type is unsupported`);
  }
  if (!SUPPORTED_OPERATORS.includes(condition.operator)) {
    errors.push(`${prefix}.operator is unsupported`);
  }
  if (condition.type === "price" && !isFiniteNumber(condition.target)) {
    errors.push(`${prefix}.target must be numeric`);
  }
  if (condition.type === "sma_cross") {
    const window = Number.parseInt(condition.window, 10);
    if (!SUPPORTED_SMA_WINDOWS.includes(window)) {
      errors.push(`${prefix}.window must be one of ${SUPPORTED_SMA_WINDOWS.join(", ")}`);
    }
  }
}

function normalizeUsExchange(exchange) {
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

function isFiniteNumber(value) {
  return value !== "" && Number.isFinite(Number(value));
}

function stockKeyFor(stock) {
  const market = String(stock.market || "").trim().toUpperCase();
  const ticker = String(stock.ticker || "").trim().toUpperCase();
  const exchange = String(stock.exchange || "").trim().toUpperCase();
  return market === "US" && exchange ? `${market}:${exchange}:${ticker}` : `${market}:${ticker}`;
}
