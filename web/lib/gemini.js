const DEFAULT_GEMINI_MODEL = "gemini-2.5-flash";

export const NATURAL_ALERT_SCHEMA = {
  type: "object",
  properties: {
    stock_query: {
      type: "string",
      description: "종목명 또는 티커. 예: 삼성전자, 애플, AAPL, 구글",
    },
    symbol_candidates: {
      type: "array",
      description: "사용자 문장의 한국어/영어 기업명을 보고 추리한 상장 종목 후보. 확실하지 않으면 여러 후보를 넣고, 모르면 빈 배열.",
      items: {
        type: "object",
        properties: {
          ticker: {
            type: "string",
            description: "상장 티커 또는 국내 6자리 종목코드. 예: AAPL, GOOGL, 066570.",
          },
          market: {
            type: "string",
            enum: ["", "KR", "US"],
            description: "국내 종목이면 KR, 미국 종목이면 US. 모르면 빈 문자열.",
          },
          exchange: {
            type: "string",
            description: "미국 종목의 거래소 후보. NASD, NYSE, AMEX 중 알면 입력하고 모르면 빈 문자열.",
          },
          company_name: {
            type: "string",
            description: "후보 회사명. 예: Apple, Alphabet, LG전자.",
          },
          confidence: {
            type: "number",
            description: "0부터 1 사이의 주관적 확신도.",
          },
        },
        required: ["ticker", "market", "exchange", "company_name", "confidence"],
      },
    },
    market_hint: {
      type: "string",
      enum: ["", "KR", "US"],
      description: "사용자가 국내/미국 시장을 명시했을 때만 KR 또는 US. 불명확하면 빈 문자열.",
    },
    condition_type: {
      type: "string",
      enum: ["price", "sma_cross", "unknown"],
      description: "가격 조건이면 price, 이동평균선 조건이면 sma_cross.",
    },
    operator: {
      type: "string",
      enum: ["", ">=", "<="],
      description: "이상/돌파/회복/넘으면은 >=, 이하/하락/깨지면/아래는 <=. 방향이 없으면 빈 문자열.",
    },
    target: {
      type: ["number", "null"],
      description: "가격 조건의 목표가. 만원, 달러 등 단위를 숫자로 환산.",
    },
    window: {
      type: ["integer", "null"],
      description: "이동평균선 기간. 지원 값은 20, 60, 240, 480.",
    },
    needs_clarification: {
      type: "boolean",
      description: "종목, 조건 종류, 방향, 값 중 저장에 필요한 정보가 부족하면 true.",
    },
    clarification_reason: {
      type: "string",
      description: "확인이 필요한 이유를 한국어로 짧게 작성.",
    },
  },
  required: [
    "stock_query",
    "symbol_candidates",
    "market_hint",
    "condition_type",
    "operator",
    "target",
    "window",
    "needs_clarification",
    "clarification_reason",
  ],
};

export async function parseNaturalAlert(text) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error("GEMINI_API_KEY is not configured");
  }
  const model = process.env.GEMINI_MODEL || DEFAULT_GEMINI_MODEL;
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-goog-api-key": apiKey,
      },
      body: JSON.stringify({
        contents: [{ parts: [{ text: buildPrompt(text) }] }],
        generationConfig: {
          responseMimeType: "application/json",
          responseJsonSchema: NATURAL_ALERT_SCHEMA,
        },
      }),
    },
  );
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Gemini parse failed: ${response.status} ${body}`);
  }
  const payload = await response.json();
  const parsedText = extractText(payload);
  if (!parsedText) {
    throw new Error("Gemini response did not include JSON text");
  }
  return JSON.parse(parsedText);
}

function buildPrompt(text) {
  return `
너는 주식 알림 조건 설정 문장을 JSON으로 변환하는 파서다.
지원하는 조건은 두 가지뿐이다.

1. price: 현재가가 특정 가격 이상 또는 이하일 때
2. sma_cross: 현재가가 20일선, 60일선, 240일선, 480일선 이상 또는 이하일 때

규칙:
- 종목명 또는 티커를 stock_query에 넣는다.
- 한국어 기업명 또는 별칭을 보고 가능한 상장 종목 후보를 symbol_candidates에 넣는다.
- 예: 애플 -> AAPL/US/Apple, 구글 -> GOOGL 또는 GOOG/US/Alphabet, 테슬라 -> TSLA/US/Tesla, 엘지전자 -> 066570/KR/LG전자.
- 후보가 여러 개일 수 있으면 최대 5개까지 넣는다. 예: LG -> LG, LG전자, LG화학 등.
- 모르는 기업명이나 너무 추상적인 표현이면 symbol_candidates는 빈 배열로 둔다.
- symbol_candidates는 추리일 뿐이며 최종 검증은 외부 종목 마스터에서 한다.
- 국내/미국 시장이 명확히 언급되지 않으면 market_hint는 빈 문자열이다.
- "이상", "넘으면", "돌파", "회복"은 operator ">="로 해석한다.
- "이하", "아래", "하락", "깨지면", "내려가면"은 operator "<="로 해석한다.
- "도달하면"처럼 방향이 없는 표현은 operator를 빈 문자열로 두고 needs_clarification을 true로 둔다.
- 이동평균선 기간이 20, 60, 240, 480 중 하나가 아니면 needs_clarification을 true로 둔다.
- 가격의 "8만원", "6만 원"은 80000, 60000처럼 숫자로 환산한다.
- 조건 저장에 필요한 정보가 부족하면 임의로 추정하지 않는다.

사용자 문장:
${text}
`.trim();
}

function extractText(payload) {
  return payload?.candidates?.[0]?.content?.parts
    ?.map((part) => part.text || "")
    .join("")
    .trim();
}
