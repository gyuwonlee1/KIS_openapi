export const SUPPORTED_MARKETS = ["KR", "US"];
export const SUPPORTED_CONDITION_TYPES = ["price", "sma_cross"];
export const SUPPORTED_OPERATORS = [">=", "<="];
export const SUPPORTED_US_EXCHANGES = ["NASD", "NASDAQ", "NAS", "NYSE", "NYS", "AMEX", "AMS"];

export function emptyPortfolio() {
  return { stocks: [] };
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
  const id = `condition-${Date.now()}`;
  if (type === "sma_cross") {
    return {
      id,
      type,
      operator: ">=",
      window: 20,
      delete_after_alert: false,
    };
  }
  return {
    id,
    type: "price",
    operator: ">=",
    target: 0,
    delete_after_alert: false,
  };
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
        next.exchange = String(stock.exchange || "").trim().toUpperCase();
      }
      return next;
    }),
  };
}

function normalizeCondition(condition) {
  const next = {
    id: String(condition.id || "").trim(),
    type: String(condition.type || "").trim(),
    operator: String(condition.operator || "").trim(),
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
  if (condition.cooldown_minutes !== undefined && condition.cooldown_minutes !== "") {
    next.cooldown_minutes = Number.parseInt(condition.cooldown_minutes, 10);
  }
  if (condition.delete_after_alert) {
    next.delete_after_alert = true;
  }
  return next;
}

function validateStock(stock, prefix, errors) {
  if (!stock || typeof stock !== "object" || Array.isArray(stock)) {
    errors.push(`${prefix} must be an object`);
    return;
  }
  if (!String(stock.name || "").trim()) {
    errors.push(`${prefix}.name is required`);
  }
  if (!String(stock.ticker || "").trim()) {
    errors.push(`${prefix}.ticker is required`);
  }

  const market = String(stock.market || "").trim().toUpperCase();
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
    if (!Number.isInteger(window) || window <= 0) {
      errors.push(`${prefix}.window must be a positive integer`);
    }
  }
  if (
    condition.cooldown_minutes !== undefined &&
    condition.cooldown_minutes !== "" &&
    (!Number.isInteger(Number(condition.cooldown_minutes)) || Number(condition.cooldown_minutes) < 0)
  ) {
    errors.push(`${prefix}.cooldown_minutes must be zero or positive`);
  }
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
