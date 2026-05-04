"use client";

import { useEffect, useMemo, useState } from "react";
import {
  SUPPORTED_OPERATORS,
  SUPPORTED_SMA_WINDOWS,
  createCondition,
  createStockFromSymbol,
  emptyPortfolio,
  updateConditionDraft,
  validatePortfolio,
} from "@/lib/portfolio";

const MARKET_LABELS = {
  ALL: "전체",
  KR: "국내",
  US: "미국",
};

export default function PortfolioEditor() {
  const [authorized, setAuthorized] = useState(false);
  const [password, setPassword] = useState("");
  const [portfolio, setPortfolio] = useState(emptyPortfolio());
  const [sha, setSha] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [status, setStatus] = useState("로그인이 필요합니다.");
  const [errors, setErrors] = useState([]);
  const selectedStock = portfolio.stocks[selectedIndex] || null;
  const validationErrors = useMemo(() => validatePortfolio(portfolio), [portfolio]);

  useEffect(() => {
    fetch("/api/session")
      .then((response) => response.json())
      .then((data) => {
        if (data.authorized) {
          setAuthorized(true);
          loadPortfolio();
        }
      })
      .catch(() => setStatus("세션 확인에 실패했습니다."));
  }, []);

  async function login(event) {
    event.preventDefault();
    setStatus("로그인 중입니다.");
    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      setStatus("비밀번호가 올바르지 않습니다.");
      return;
    }
    setAuthorized(true);
    setPassword("");
    await loadPortfolio();
  }

  async function logout() {
    await fetch("/api/session", { method: "DELETE" });
    setAuthorized(false);
    setPortfolio(emptyPortfolio());
    setStatus("로그아웃했습니다.");
  }

  async function loadPortfolio() {
    setStatus("포트폴리오를 불러오는 중입니다.");
    setErrors([]);
    const response = await fetch("/api/portfolio", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) {
      setStatus("포트폴리오를 불러오지 못했습니다.");
      setErrors([data.error || "알 수 없는 오류"]);
      return;
    }
    setPortfolio(data.portfolio || emptyPortfolio());
    setSha(data.sha || "");
    setSelectedIndex(0);
    setStatus(`${data.repo} ${data.branch} 브랜치에서 불러왔습니다.`);
  }

  async function savePortfolio(message = "Update portfolio from web editor") {
    await savePortfolioSnapshot(portfolio, message);
  }

  async function savePortfolioSnapshot(nextPortfolio, message) {
    const currentErrors = validatePortfolio(nextPortfolio);
    setErrors(currentErrors);
    if (currentErrors.length > 0) {
      setStatus("저장 전에 수정해야 할 항목이 있습니다.");
      return;
    }
    setStatus("GitHub에 저장 중입니다.");
    const response = await fetch("/api/portfolio", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ portfolio: nextPortfolio, sha, message }),
    });
    const data = await response.json();
    if (!response.ok) {
      setStatus("저장에 실패했습니다.");
      setErrors(data.errors || [data.error || "알 수 없는 오류"]);
      return;
    }
    setStatus(`저장되었습니다. commit ${data.commitSha || ""}`);
    await loadPortfolio();
  }

  function addStockFromSearch(symbol) {
    const stock = createStockFromSymbol(symbol);
    const nextIndex = portfolio.stocks.length;
    setPortfolio((current) => ({ ...current, stocks: [...current.stocks, stock] }));
    setSelectedIndex(nextIndex);
    setErrors([]);
    setStatus(`${stock.name}을(를) 관심 종목에 추가했습니다.`);
  }

  function updateStock(patch) {
    setPortfolio((current) => ({
      ...current,
      stocks: current.stocks.map((stock, index) =>
        index === selectedIndex ? { ...stock, ...patch } : stock,
      ),
    }));
  }

  function updateCondition(conditionIndex, patch) {
    const conditions = Array.isArray(selectedStock.conditions) ? selectedStock.conditions : [];
    updateStock({
      conditions: conditions.map((condition, index) => {
        if (index !== conditionIndex) {
          return updateConditionDraft(condition, {});
        }
        if (patch.__replace) {
          return updateConditionDraft(patch.condition, {});
        }
        return updateConditionDraft(condition, patch);
      }),
    });
  }

  function removeStock() {
    const nextPortfolio = {
      ...portfolio,
      stocks: portfolio.stocks.filter((_, index) => index !== selectedIndex),
    };
    setPortfolio(nextPortfolio);
    setSelectedIndex(Math.max(0, selectedIndex - 1));
    void savePortfolioSnapshot(nextPortfolio, "Remove stock from web editor");
  }

  function addCondition(type) {
    const conditions = Array.isArray(selectedStock.conditions) ? selectedStock.conditions : [];
    updateStock({ conditions: [...conditions.map((condition) => updateConditionDraft(condition, {})), createCondition(type)] });
  }

  function removeCondition(conditionIndex) {
    const conditions = Array.isArray(selectedStock.conditions) ? selectedStock.conditions : [];
    updateStock({
      conditions: conditions
        .filter((_, index) => index !== conditionIndex)
        .map((condition) => updateConditionDraft(condition, {})),
    });
  }

  if (!authorized) {
    return (
      <main className="login">
        <section className="panel login-panel">
          <div className="panel-header">
            <h1>KIS 알림 설정</h1>
          </div>
          <form className="login-form" onSubmit={login}>
            <label>
              관리자 비밀번호
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
              />
            </label>
            <button className="primary" type="submit">
              로그인
            </button>
            <p className="status">{status}</p>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <h1>KIS 알림 설정</h1>
          <span>검색으로 종목을 추가하고, 1회성 알림 조건을 관리합니다.</span>
        </div>
        <div className="toolbar">
          <span className="status">{status}</span>
          <button type="button" onClick={loadPortfolio}>
            새로고침
          </button>
          <button type="button" onClick={logout}>
            로그아웃
          </button>
        </div>
      </header>

      <div className="layout">
        <section className="panel">
          <div className="panel-header">
            <h2>종목 검색</h2>
          </div>
          <SymbolSearch onSelect={addStockFromSearch} />

          <div className="panel-header subtle">
            <h2>관심 종목</h2>
          </div>
          <div className="stock-list">
            {portfolio.stocks.length === 0 ? (
              <p className="empty">검색 결과에서 종목을 선택해 추가하세요.</p>
            ) : null}
            {portfolio.stocks.map((stock, index) => (
              <button
                className={`stock-row ${index === selectedIndex ? "active" : ""}`}
                type="button"
                key={`${stock.market}-${stock.exchange || ""}-${stock.ticker}-${index}`}
                onClick={() => setSelectedIndex(index)}
              >
                <span className="stock-name">
                  <strong>{stock.name || "이름 없음"}</strong>
                  <span className="meta">{formatStockMeta(stock)}</span>
                </span>
                <span className={`badge ${stock.enabled ? "enabled" : ""}`}>
                  {stock.enabled ? "활성" : "중지"}
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>알림 조건</h2>
            {selectedStock ? (
              <div className="toolbar">
                <button
                  className="primary"
                  type="button"
                  onClick={() => savePortfolio(`Update ${selectedStock.name} conditions from web editor`)}
                >
                  이 종목 저장
                </button>
                <button className="danger" type="button" onClick={removeStock}>
                  종목 삭제
                </button>
              </div>
            ) : null}
          </div>

          {selectedStock ? (
            <div className="editor">
              <section className="readonly-stock">
                <div>
                  <span className="field-label">선택한 종목</span>
                  <strong>{selectedStock.name}</strong>
                </div>
                <div>
                  <span className="field-label">티커</span>
                  <strong>{selectedStock.ticker}</strong>
                </div>
                <div>
                  <span className="field-label">시장</span>
                  <strong>{formatMarket(selectedStock)}</strong>
                </div>
              </section>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={selectedStock.enabled}
                  onChange={(event) => updateStock({ enabled: event.target.checked })}
                />
                이 종목 알림 활성화
              </label>

              <section className="conditions">
                <div className="panel-header inline">
                  <h3>조건 목록</h3>
                  <div className="toolbar">
                    <button type="button" onClick={() => addCondition("price")}>
                      가격 조건 추가
                    </button>
                    <button type="button" onClick={() => addCondition("sma_cross")}>
                      이동평균선 조건 추가
                    </button>
                  </div>
                </div>

                {(selectedStock.conditions || []).map((condition, conditionIndex) => (
                  <ConditionEditor
                    condition={condition}
                    key={`${condition.id}-${conditionIndex}`}
                    onChange={(patch) => updateCondition(conditionIndex, patch)}
                    onRemove={() => removeCondition(conditionIndex)}
                  />
                ))}
                {(selectedStock.conditions || []).length === 0 ? (
                  <p className="empty">설정된 조건이 없습니다. 필요한 조건을 추가하세요.</p>
                ) : null}
              </section>

              <p className="hint">모든 조건은 최초 도달 시 한 번 알림을 보낸 뒤 자동 삭제됩니다.</p>

              {validationErrors.length > 0 || errors.length > 0 ? (
                <div className="error-box">
                  <strong>검증 오류</strong>
                  <ul>
                    {[...validationErrors, ...errors].map((error) => (
                      <li key={error}>{error}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="editor">
              <p className="empty">왼쪽에서 종목을 검색해 관심 종목에 추가하세요.</p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function SymbolSearch({ onSelect }) {
  const [query, setQuery] = useState("");
  const [market, setMarket] = useState("ALL");
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("종목명이나 티커를 입력하세요.");

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResults([]);
      setStatus("종목명이나 티커를 입력하세요.");
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setStatus("검색 중입니다.");
      const params = new URLSearchParams({ q });
      if (market !== "ALL") {
        params.set("market", market);
      }
      try {
        const response = await fetch(`/api/symbols?${params.toString()}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok) {
          setStatus(data.error || "검색에 실패했습니다.");
          setResults([]);
          return;
        }
        setResults(data.symbols || []);
        setStatus(data.symbols?.length ? `${data.symbols.length}개 종목을 찾았습니다.` : "검색 결과가 없습니다.");
      } catch (error) {
        if (error.name !== "AbortError") {
          setStatus("검색에 실패했습니다.");
          setResults([]);
        }
      }
    }, 250);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query, market]);

  return (
    <div className="symbol-search">
      <div className="search-grid">
        <label>
          종목 검색
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="예: 삼성전자, Apple, AAPL"
          />
        </label>
        <label>
          시장
          <select value={market} onChange={(event) => setMarket(event.target.value)}>
            {Object.entries(MARKET_LABELS).map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="status">{status}</p>
      <div className="search-results">
        {results.map((symbol) => (
          <button
            className="search-result"
            type="button"
            key={`${symbol.market}-${symbol.exchange || ""}-${symbol.ticker}`}
            onClick={() => onSelect(symbol)}
          >
            <span>
              <strong>{symbol.name}</strong>
              <span className="meta">{formatSymbolMeta(symbol)}</span>
            </span>
            <span className="badge enabled">선택</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ConditionEditor({ condition, onChange, onRemove }) {
  const type = condition.type === "sma_cross" ? "sma_cross" : "price";
  const smaWindow = SUPPORTED_SMA_WINDOWS.includes(Number(condition.window)) ? Number(condition.window) : "";

  return (
    <div className="condition">
      <div className="condition-title">
        <strong>{type === "price" ? "가격 조건" : "이동평균선 조건"}</strong>
        <button className="danger" type="button" onClick={onRemove}>
          조건 삭제
        </button>
      </div>

      <div className="grid">
        <label>
          조건 종류
          <select
            value={type}
            onChange={(event) => onChange({ __replace: true, condition: createCondition(event.target.value) })}
          >
            <option value="price">가격</option>
            <option value="sma_cross">이동평균선</option>
          </select>
        </label>
        <label>
          방향
          <select value={condition.operator} onChange={(event) => onChange({ operator: event.target.value })}>
            {SUPPORTED_OPERATORS.map((operator) => (
              <option value={operator} key={operator}>
                {operator === ">=" ? "이상" : "이하"}
              </option>
            ))}
          </select>
        </label>
        {type === "price" ? (
          <label>
            목표가
            <input
              type="number"
              value={condition.target ?? ""}
              onChange={(event) => onChange({ target: event.target.value })}
            />
          </label>
        ) : (
          <label>
            이동평균선
            <select value={smaWindow} onChange={(event) => onChange({ window: event.target.value })}>
              <option value="" disabled>
                선택 필요
              </option>
              {SUPPORTED_SMA_WINDOWS.map((window) => (
                <option value={window} key={window}>
                  {window}일선
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </div>
  );
}

function formatStockMeta(stock) {
  return `${formatMarket(stock)} ${stock.ticker}`;
}

function formatSymbolMeta(symbol) {
  return `${formatMarket(symbol)} ${symbol.ticker}`;
}

function formatMarket(stock) {
  if (stock.market === "KR") {
    return stock.exchange ? `국내 ${stock.exchange}` : "국내";
  }
  return `${stock.exchange || "US"} 미국`;
}
