import assert from "node:assert/strict";

import {
  applyConditionToPortfolio,
  decodeConfirmId,
  encodeConfirmId,
  formatConditionSummary,
  resolveParsedAlert,
} from "../lib/natural-alert.js";

function test(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    throw error;
  }
}

test("resolves a Gemini price parse into a verified one-shot condition", () => {
  const resolved = resolveParsedAlert({
    stock_query: "삼성전자",
    market_hint: "KR",
    condition_type: "price",
    operator: ">=",
    target: 80000,
    window: null,
    needs_clarification: false,
    clarification_reason: "",
  });

  assert.equal(resolved.ok, true);
  assert.equal(resolved.symbol.ticker, "005930");
  assert.equal(resolved.condition.type, "price");
  assert.equal(resolved.condition.delete_after_alert, true);
});

test("requires a clear direction before saving natural language alerts", () => {
  const resolved = resolveParsedAlert({
    stock_query: "삼성전자",
    market_hint: "KR",
    condition_type: "sma_cross",
    operator: "",
    target: null,
    window: 60,
    needs_clarification: false,
    clarification_reason: "",
  });

  assert.equal(resolved.ok, false);
  assert.match(resolved.message, /이상인지 이하인지/);
});

test("encodes compact confirmation payloads and decodes verified symbols", () => {
  const resolved = resolveParsedAlert({
    stock_query: "AAPL",
    market_hint: "US",
    condition_type: "sma_cross",
    operator: "<=",
    target: null,
    window: 60,
    needs_clarification: false,
    clarification_reason: "",
  });

  const customId = encodeConfirmId(resolved.symbol, resolved.condition);
  const decoded = decodeConfirmId(customId);

  assert.ok(customId.length <= 100);
  assert.equal(decoded.symbol.ticker, "AAPL");
  assert.equal(decoded.condition.type, "sma_cross");
  assert.equal(decoded.condition.window, 60);
});

test("applies a Discord condition to an existing portfolio stock", () => {
  const resolved = resolveParsedAlert({
    stock_query: "삼성전자",
    market_hint: "KR",
    condition_type: "price",
    operator: "<=",
    target: 60000,
    window: null,
    needs_clarification: false,
    clarification_reason: "",
  });
  const portfolio = {
    stocks: [
      {
        name: "삼성전자",
        ticker: "005930",
        market: "KR",
        enabled: false,
        conditions: [],
      },
    ],
  };

  const next = applyConditionToPortfolio(portfolio, resolved.symbol, resolved.condition);

  assert.equal(next.stocks.length, 1);
  assert.equal(next.stocks[0].enabled, true);
  assert.equal(next.stocks[0].conditions.length, 1);
  assert.equal(next.stocks[0].conditions[0].target, 60000);
});

test("formats a Korean confirmation summary", () => {
  const resolved = resolveParsedAlert({
    stock_query: "삼성전자",
    market_hint: "KR",
    condition_type: "price",
    operator: ">=",
    target: 80000,
    window: null,
    needs_clarification: false,
    clarification_reason: "",
  });

  assert.equal(
    formatConditionSummary(resolved.symbol, resolved.condition),
    "삼성전자 (005930): 현재가가 80,000원 이상일 때",
  );
});
