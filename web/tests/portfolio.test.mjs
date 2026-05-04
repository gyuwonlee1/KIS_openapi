import assert from "node:assert/strict";

import {
  SUPPORTED_SMA_WINDOWS,
  createCondition,
  normalizePortfolio,
  updateConditionDraft,
  validatePortfolio,
} from "../lib/portfolio.js";
import { findSymbol, searchSymbols, validateSymbolsInPortfolio } from "../lib/symbols.js";

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

test("allows a verified stock without conditions", () => {
  const errors = validatePortfolio({
    stocks: [
      {
        name: "삼성전자",
        ticker: "005930",
        market: "KR",
        enabled: true,
        conditions: [],
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

test("normalizes every condition as one-shot and removes cooldown", () => {
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
          },
        ],
      },
    ],
  });

  const condition = normalized.stocks[0].conditions[0];
  assert.equal(normalized.stocks[0].ticker, "AAPL");
  assert.equal(normalized.stocks[0].exchange, "NASD");
  assert.equal(condition.window, 60);
  assert.equal(condition.delete_after_alert, true);
  assert.equal("cooldown_minutes" in condition, false);
});

test("creates a default one-shot SMA condition", () => {
  const condition = createCondition("sma_cross");
  assert.equal(condition.type, "sma_cross");
  assert.equal(condition.window, 20);
  assert.equal(condition.delete_after_alert, true);
});

test("keeps condition id while editing numeric target drafts", () => {
  const condition = {
    id: "target",
    type: "price",
    operator: ">=",
    target: "1",
    delete_after_alert: true,
  };

  const updated = updateConditionDraft(condition, { target: "12" });

  assert.equal(updated.id, "target");
  assert.equal(updated.target, "12");
});

test("allows only the supported SMA windows", () => {
  assert.deepEqual(SUPPORTED_SMA_WINDOWS, [20, 60, 240, 480]);

  const errors = validatePortfolio({
    stocks: [
      {
        name: "삼성전자",
        ticker: "005930",
        market: "KR",
        enabled: true,
        conditions: [{ id: "sma", type: "sma_cross", operator: ">=", window: 5 }],
      },
    ],
  });

  assert.ok(errors.some((error) => error.includes("window")));
});

test("searches verified Korean and US symbols", () => {
  const samsung = searchSymbols("삼성전자", "KR");
  const apple = searchSymbols("AAPL", "US");

  assert.equal(samsung[0].ticker, "005930");
  assert.equal(apple[0].ticker, "AAPL");
  assert.equal(apple[0].exchange, "NASD");
});

test("searches symbols with spacing, compact Korean aliases, and translated US names", () => {
  assert.equal(searchSymbols("lg 전자", "KR")[0].ticker, "066570");
  assert.equal(searchSymbols("엘지전자", "KR")[0].ticker, "066570");
  assert.equal(searchSymbols("애플", "US")[0].ticker, "AAPL");
  assert.equal(searchSymbols("구글", "US")[0].ticker, "GOOGL");
  assert.equal(searchSymbols("테슬라", "US")[0].ticker, "TSLA");
  assert.equal(searchSymbols("엔비디아", "US")[0].ticker, "NVDA");
  assert.equal(searchSymbols("마이크로소프트", "US")[0].ticker, "MSFT");
  assert.equal(searchSymbols("GOOGL", "US")[0].ticker, "GOOGL");
});

test("validates stocks against the symbol master", () => {
  assert.ok(findSymbol({ market: "KR", ticker: "005930" }));
  assert.ok(findSymbol({ market: "US", exchange: "NASD", ticker: "AAPL" }));

  const errors = validateSymbolsInPortfolio({
    stocks: [
      {
        name: "없는종목",
        ticker: "999999",
        market: "KR",
        enabled: true,
        conditions: [{ id: "target", type: "price", operator: ">=", target: 1000 }],
      },
    ],
  });

  assert.equal(errors.length, 1);
});
