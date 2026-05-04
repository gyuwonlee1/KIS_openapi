import {
  SUPPORTED_SMA_WINDOWS,
  newConditionId,
  normalizePortfolio,
  validatePortfolio,
} from "./portfolio.js";
import { findSymbol, searchSymbols, validateSymbolsInPortfolio } from "./symbols.js";

const CONFIRM_PREFIX = "kisac:";
const CANCEL_PREFIX = "kis_alert_cancel";

export function resolveParsedAlert(parsed) {
  const stockQuery = String(parsed?.stock_query || "").trim();
  const conditionType = String(parsed?.condition_type || "").trim();
  const operator = String(parsed?.operator || "").trim();

  if (parsed?.needs_clarification) {
    return failure(parsed.clarification_reason || "조건을 저장하기 위한 정보가 부족합니다.");
  }
  if (!stockQuery) {
    return failure("종목명을 찾지 못했습니다. 예: 삼성전자 8만원 이상");
  }
  if (!["price", "sma_cross"].includes(conditionType)) {
    return failure("지원하는 조건은 가격 조건과 이동평균선 조건뿐입니다.");
  }
  if (![">=", "<="].includes(operator)) {
    return failure("조건 방향을 확인해 주세요. 이상인지 이하인지 함께 입력해 주세요.");
  }

  const symbolResult = resolveSymbol(stockQuery, parsed?.market_hint);
  if (!symbolResult.ok) {
    return symbolResult;
  }

  const condition = buildCondition(parsed, conditionType, operator);
  if (!condition.ok) {
    return condition;
  }

  return {
    ok: true,
    symbol: symbolResult.symbol,
    condition: condition.condition,
    summary: formatConditionSummary(symbolResult.symbol, condition.condition),
  };
}

export function applyConditionToPortfolio(portfolio, symbol, condition) {
  const normalized = normalizePortfolio(portfolio);
  const next = {
    stocks: normalized.stocks.map((stock) => ({
      ...stock,
      conditions: [...(stock.conditions || [])],
    })),
  };
  const index = next.stocks.findIndex((stock) => stockKey(stock) === stockKey(symbol));
  if (index >= 0) {
    next.stocks[index] = {
      ...next.stocks[index],
      enabled: true,
      conditions: [...next.stocks[index].conditions, condition],
    };
  } else {
    const stock = {
      name: symbol.name,
      ticker: symbol.ticker,
      market: symbol.market,
      enabled: true,
      conditions: [condition],
    };
    if (symbol.market === "US") {
      stock.exchange = symbol.exchange;
    }
    next.stocks.push(stock);
  }

  const errors = [...validatePortfolio(next), ...validateSymbolsInPortfolio(next)];
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
  return normalizePortfolio(next);
}

export function encodeConfirmId(symbol, condition) {
  const operator = condition.operator === ">=" ? "gte" : "lte";
  const value = condition.type === "price" ? condition.target : condition.window;
  return [
    CONFIRM_PREFIX,
    symbol.market,
    symbol.exchange || "",
    symbol.ticker,
    condition.type,
    operator,
    value,
  ].join("|");
}

export function decodeConfirmId(customId) {
  if (!String(customId || "").startsWith(CONFIRM_PREFIX)) {
    return null;
  }
  const [, market, exchange, ticker, type, operatorValue, value] = String(customId).split("|");
  const symbol = {
    ticker,
    market,
    exchange: exchange || undefined,
  };
  const verifiedSymbol = findSymbol(symbol);
  if (!verifiedSymbol) {
    throw new Error("확인된 종목 마스터에서 종목을 찾지 못했습니다.");
  }
  const condition = {
    id: newConditionId(type),
    type,
    operator: operatorValue === "gte" ? ">=" : "<=",
    delete_after_alert: true,
  };
  if (condition.type === "price") {
    condition.target = Number(value);
  }
  if (condition.type === "sma_cross") {
    condition.window = Number.parseInt(value, 10);
  }
  return { symbol: verifiedSymbol, condition };
}

export function isCancelId(customId) {
  return customId === CANCEL_PREFIX;
}

export function confirmationComponents(symbol, condition) {
  return [
    {
      type: 1,
      components: [
        {
          type: 2,
          style: 3,
          label: "저장",
          custom_id: encodeConfirmId(symbol, condition),
        },
        {
          type: 2,
          style: 4,
          label: "취소",
          custom_id: CANCEL_PREFIX,
        },
      ],
    },
  ];
}

export function confirmationMessage(symbol, condition) {
  return `아래 조건을 저장할까요?\n\n${formatConditionSummary(symbol, condition)}\n\n저장된 조건은 최초 알림 후 자동 삭제됩니다.`;
}

export function formatConditionSummary(symbol, condition) {
  const stock = `${symbol.name} (${symbol.ticker})`;
  if (condition.type === "price") {
    return `${stock}: 현재가가 ${formatPrice(condition.target, symbol.market)} ${operatorText(condition.operator)}일 때`;
  }
  return `${stock}: 현재가가 ${condition.window}일 이동평균선 ${operatorText(condition.operator)}일 때`;
}

function resolveSymbol(stockQuery, marketHint) {
  const candidates = searchSymbols(stockQuery, marketHint);
  if (candidates.length === 0) {
    return failure(`"${stockQuery}"에 해당하는 종목을 찾지 못했습니다.`);
  }

  const normalizedQuery = normalizeSearchText(stockQuery);
  const exact = candidates.filter(
    (symbol) =>
      normalizeSearchText(symbol.ticker) === normalizedQuery ||
      normalizeSearchText(symbol.name) === normalizedQuery,
  );
  if (exact.length === 1) {
    return { ok: true, symbol: exact[0] };
  }
  if (candidates.length === 1) {
    return { ok: true, symbol: candidates[0] };
  }

  const options = candidates
    .slice(0, 5)
    .map((symbol) => `${symbol.name} (${symbol.ticker}, ${symbol.market}${symbol.exchange ? `/${symbol.exchange}` : ""})`)
    .join("\n");
  return failure(`종목 후보가 여러 개입니다. 더 정확히 입력해 주세요.\n\n${options}`);
}

function buildCondition(parsed, conditionType, operator) {
  if (conditionType === "price") {
    const target = Number(parsed.target);
    if (!Number.isFinite(target) || target <= 0) {
      return failure("가격 조건에는 0보다 큰 목표가가 필요합니다.");
    }
    return {
      ok: true,
      condition: {
        id: newConditionId("price"),
        type: "price",
        operator,
        target,
        delete_after_alert: true,
      },
    };
  }

  const window = Number.parseInt(parsed.window, 10);
  if (!SUPPORTED_SMA_WINDOWS.includes(window)) {
    return failure(`이동평균선은 ${SUPPORTED_SMA_WINDOWS.join(", ")}일선 중 하나만 지원합니다.`);
  }
  return {
    ok: true,
    condition: {
      id: newConditionId("sma_cross"),
      type: "sma_cross",
      operator,
      window,
      delete_after_alert: true,
    },
  };
}

function failure(message) {
  return { ok: false, message };
}

function stockKey(stock) {
  if (stock.market === "US" && stock.exchange) {
    return `${stock.market}:${stock.exchange}:${stock.ticker}`;
  }
  return `${stock.market}:${stock.ticker}`;
}

function normalizeSearchText(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, " ");
}

function operatorText(operator) {
  return operator === ">=" ? "이상" : "이하";
}

function formatPrice(value, market) {
  if (market === "KR") {
    return `${Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`;
  }
  if (market === "US") {
    return `$${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return String(value);
}
