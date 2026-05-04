"use client";

import { useEffect, useMemo, useState } from "react";
import {
  SUPPORTED_OPERATORS,
  createCondition,
  createStock,
  emptyPortfolio,
  validatePortfolio,
} from "@/lib/portfolio";

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
    setStatus("로그아웃되었습니다.");
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

  async function savePortfolio() {
    const currentErrors = validatePortfolio(portfolio);
    setErrors(currentErrors);
    if (currentErrors.length > 0) {
      setStatus("저장 전 수정이 필요한 항목이 있습니다.");
      return;
    }
    setStatus("GitHub에 저장 중입니다.");
    const response = await fetch("/api/portfolio", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        portfolio,
        sha,
        message: "Update portfolio from web editor",
      }),
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

  function updateStock(patch) {
    setPortfolio((current) => ({
      ...current,
      stocks: current.stocks.map((stock, index) =>
        index === selectedIndex ? { ...stock, ...patch } : stock,
      ),
    }));
  }

  function updateCondition(conditionIndex, patch) {
    updateStock({
      conditions: selectedStock.conditions.map((condition, index) =>
        index === conditionIndex ? normalizeConditionPatch(condition, patch) : condition,
      ),
    });
  }

  function addStock() {
    const stock = createStock();
    setPortfolio((current) => ({ ...current, stocks: [...current.stocks, stock] }));
    setSelectedIndex(portfolio.stocks.length);
  }

  function removeStock() {
    setPortfolio((current) => ({
      ...current,
      stocks: current.stocks.filter((_, index) => index !== selectedIndex),
    }));
    setSelectedIndex(Math.max(0, selectedIndex - 1));
  }

  function addCondition(type) {
    updateStock({ conditions: [...selectedStock.conditions, createCondition(type)] });
  }

  function removeCondition(conditionIndex) {
    updateStock({
      conditions: selectedStock.conditions.filter((_, index) => index !== conditionIndex),
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
          <span>portfolio.json 편집기</span>
        </div>
        <div className="toolbar">
          <span className="status">{status}</span>
          <button type="button" onClick={loadPortfolio}>
            새로고침
          </button>
          <button className="primary" type="button" onClick={savePortfolio}>
            저장
          </button>
          <button type="button" onClick={logout}>
            로그아웃
          </button>
        </div>
      </header>

      <div className="layout">
        <section className="panel">
          <div className="panel-header">
            <h2>종목</h2>
            <button className="icon" type="button" title="종목 추가" onClick={addStock}>
              +
            </button>
          </div>
          <div className="stock-list">
            {portfolio.stocks.map((stock, index) => (
              <button
                className={`stock-row ${index === selectedIndex ? "active" : ""}`}
                type="button"
                key={`${stock.market}-${stock.ticker}-${index}`}
                onClick={() => setSelectedIndex(index)}
              >
                <span className="stock-name">
                  <strong>{stock.name || "이름 없음"}</strong>
                  <span className="meta">
                    {stock.market} {stock.exchange ? `${stock.exchange} ` : ""}
                    {stock.ticker || "티커 없음"}
                  </span>
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
            <h2>조건 편집</h2>
            {selectedStock ? (
              <button className="danger" type="button" onClick={removeStock}>
                종목 삭제
              </button>
            ) : null}
          </div>

          {selectedStock ? (
            <div className="editor">
              <div className="grid">
                <label>
                  종목명
                  <input
                    value={selectedStock.name}
                    onChange={(event) => updateStock({ name: event.target.value })}
                  />
                </label>
                <label>
                  티커
                  <input
                    value={selectedStock.ticker}
                    onChange={(event) => updateStock({ ticker: event.target.value.toUpperCase() })}
                  />
                </label>
                <label>
                  시장
                  <select
                    value={selectedStock.market}
                    onChange={(event) =>
                      updateStock({
                        market: event.target.value,
                        exchange: event.target.value === "US" ? selectedStock.exchange || "NASD" : undefined,
                      })
                    }
                  >
                    <option value="KR">국내</option>
                    <option value="US">미국</option>
                  </select>
                </label>
                {selectedStock.market === "US" ? (
                  <label>
                    거래소
                    <select
                      value={selectedStock.exchange || "NASD"}
                      onChange={(event) => updateStock({ exchange: event.target.value })}
                    >
                      <option value="NASD">NASDAQ</option>
                      <option value="NYSE">NYSE</option>
                      <option value="AMEX">AMEX</option>
                    </select>
                  </label>
                ) : null}
              </div>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={selectedStock.enabled}
                  onChange={(event) => updateStock({ enabled: event.target.checked })}
                />
                종목 활성화
              </label>

              <section className="conditions">
                <div className="panel-header">
                  <h3>알림 조건</h3>
                  <div className="toolbar">
                    <button type="button" onClick={() => addCondition("price")}>
                      가격 조건
                    </button>
                    <button type="button" onClick={() => addCondition("sma_cross")}>
                      이동평균선 조건
                    </button>
                  </div>
                </div>

                {selectedStock.conditions.map((condition, conditionIndex) => (
                  <ConditionEditor
                    condition={condition}
                    key={`${condition.id}-${conditionIndex}`}
                    onChange={(patch) => updateCondition(conditionIndex, patch)}
                    onRemove={() => removeCondition(conditionIndex)}
                  />
                ))}
              </section>

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
              <button className="primary" type="button" onClick={addStock}>
                첫 종목 추가
              </button>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function ConditionEditor({ condition, onChange, onRemove }) {
  return (
    <div className="condition">
      <div className="condition-title">
        <strong>{condition.type === "price" ? "가격 조건" : "이동평균선 조건"}</strong>
        <button className="icon danger" type="button" title="조건 삭제" onClick={onRemove}>
          ×
        </button>
      </div>

      <div className="grid">
        <label>
          조건 ID
          <input value={condition.id} onChange={(event) => onChange({ id: event.target.value })} />
        </label>
        <label>
          조건 유형
          <select value={condition.type} onChange={(event) => onChange(createCondition(event.target.value))}>
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
        {condition.type === "price" ? (
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
            이동평균 기간
            <input
              type="number"
              min="1"
              value={condition.window ?? ""}
              onChange={(event) => onChange({ window: event.target.value })}
            />
          </label>
        )}
        <label>
          재알림 간격
          <input
            type="number"
            min="0"
            value={condition.cooldown_minutes ?? ""}
            onChange={(event) => onChange({ cooldown_minutes: event.target.value })}
          />
        </label>
      </div>

      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={Boolean(condition.delete_after_alert)}
          onChange={(event) => onChange({ delete_after_alert: event.target.checked })}
        />
        최초 알림 후 완료 처리
      </label>
    </div>
  );
}

function normalizeConditionPatch(condition, patch) {
  if (patch.type && patch.type !== condition.type) {
    return { ...patch, id: condition.id, operator: condition.operator || ">=" };
  }
  return { ...condition, ...patch };
}
