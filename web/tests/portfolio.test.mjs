import assert from "node:assert/strict";

import {
  createCondition,
  normalizePortfolio,
  validatePortfolio,
} from "../lib/portfolio.js";

function test(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    throw error;
  }
}

test("validates a portfolio with one-shot price condition", () => {
  const errors = validatePortfolio({
    stocks: [
      {
        name: "삼성전자",
        ticker: "005930",
        market: "KR",
        enabled: true,
        conditions: [
          {
            id: "target",
            type: "price",
            operator: ">=",
            target: 80000,
            delete_after_alert: true,
          },
        ],
      },
    ],
  });

  assert.deepEqual(errors, []);
});

test("rejects invalid operator and missing US exchange", () => {
  const errors = validatePortfolio({
    stocks: [
      {
        name: "애플",
        ticker: "AAPL",
        market: "US",
        enabled: true,
        conditions: [{ id: "bad", type: "price", operator: ">", target: 200 }],
      },
    ],
  });

  assert.ok(errors.some((error) => error.includes("exchange")));
  assert.ok(errors.some((error) => error.includes("operator")));
});

test("normalizes condition values before GitHub save", () => {
  const normalized = normalizePortfolio({
    stocks: [
      {
        name: " 애플 ",
        ticker: "aapl",
        market: "US",
        exchange: "nasd",
        enabled: true,
        conditions: [
          {
            id: "sma",
            type: "sma_cross",
            operator: ">=",
            window: "60",
            cooldown_minutes: "120",
            delete_after_alert: true,
          },
        ],
      },
    ],
  });

  assert.equal(normalized.stocks[0].ticker, "AAPL");
  assert.equal(normalized.stocks[0].exchange, "NASD");
  assert.equal(normalized.stocks[0].conditions[0].window, 60);
  assert.equal(normalized.stocks[0].conditions[0].delete_after_alert, true);
});

test("creates a default SMA condition", () => {
  const condition = createCondition("sma_cross");
  assert.equal(condition.type, "sma_cross");
  assert.equal(condition.window, 20);
});
