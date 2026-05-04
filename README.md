# KIS 주식 알림 봇

한국투자증권(KIS) Open API로 국내/미국 주식 가격을 확인하고, 설정한 조건을 만족하면 Discord Webhook으로 알림을 보내는 서버리스 주식 알림 봇입니다. GitHub Actions가 15분마다 실행하므로 별도 서버를 계속 켜둘 필요가 없습니다.

## 현재 개발 단계

현재는 MVP 배포 완료 단계입니다.

- GitHub Actions 15분 주기 실행
- 수동 실행(`workflow_dispatch`) 지원
- KIS 실전투자 REST API 토큰 발급
- 국내/미국 현재가 조회
- 국내/미국 일봉 조회
- 가격 조건(`price`) 평가
- 현재가와 단순이동평균선 비교 조건(`sma_cross`) 평가
- 장 시간 필터
  - 국내: 평일 09:00-15:30 KST
  - 미국: 평일 04:00-20:00 America/New_York
- 상태 파일 기반 중복 알림 방지
- 한국어 Discord Embed 알림
- 오류 요약 알림
- 유닛 테스트

아직 구현하지 않은 기능은 웹 설정 UI, Discord 명령으로 조건 추가, 자연어 조건 설정입니다.

## 설정 파일

관심 종목과 조건은 `portfolio.json`에서 관리합니다. 민감한 계좌정보나 API Key는 이 파일에 넣지 않습니다.

국내 종목 예시:

```json
{
  "name": "삼성전자",
  "ticker": "005930",
  "market": "KR",
  "enabled": true,
  "conditions": [
    {
      "id": "samsung-target-up",
      "type": "price",
      "operator": ">=",
      "target": 80000
    },
    {
      "id": "samsung-sma60-up",
      "type": "sma_cross",
      "operator": ">=",
      "window": 60
    }
  ]
}
```

미국 종목 예시:

```json
{
  "name": "애플",
  "ticker": "AAPL",
  "market": "US",
  "exchange": "NASD",
  "enabled": true,
  "conditions": [
    {
      "id": "apple-target-up",
      "type": "price",
      "operator": ">=",
      "target": 220,
      "cooldown_minutes": 120
    }
  ]
}
```

조건 타입:

- `price`: 현재가가 `target` 이상 또는 이하이면 알림
- `sma_cross`: 현재가가 `window`일 단순이동평균선 이상 또는 이하이면 알림

연산자:

- `>=`: 이상
- `<=`: 이하

`cooldown_minutes`는 선택 필드입니다. 조건이 계속 만족되는 동안에도 지정한 시간이 지나면 다시 알림을 보낼 수 있습니다. 값을 넣지 않으면 조건이 false가 되었다가 다시 true가 될 때만 재알림합니다.

`delete_after_alert`도 선택 필드입니다. `true`로 설정하면 조건이 최초로 충족되어 알림을 보낸 뒤 상태 파일에 완료 처리되고, 이후 실행에서는 평가하지 않습니다.

```json
{
  "id": "samsung-target-up",
  "type": "price",
  "operator": ">=",
  "target": 80000,
  "delete_after_alert": true
}
```

## GitHub Actions 설정

Repository Secrets에 아래 값을 등록해야 합니다.

```text
KIS_APP_KEY
KIS_APP_SECRET
DISCORD_WEBHOOK_URL
```

선택 값:

```text
KIS_BASE_URL
```

`KIS_BASE_URL`을 비워두면 실전투자 OPS 기본 URL을 사용합니다.

수동 실행할 때는 `market_hours_enabled` 입력을 선택할 수 있습니다.

- `true`: 장 시간에만 종목 조회
- `false`: 장 시간 필터를 끄고 연결 테스트

평소 운영은 `true`를 사용합니다. KIS 인증과 시세 조회 연결만 확인하고 싶을 때는 `false`로 한 번 실행할 수 있습니다.

## Discord 알림

알림은 한국어 Embed로 발송됩니다.

예시 제목:

- `삼성전자 목표가 도달`
- `삼성전자 60일 이동평균선 돌파`
- `애플 하락 기준가 도달`

알림 필드:

- 종목
- 시장
- 현재가
- 기준값
- 조건
- 감지 시각

국내 종목은 원화(`80,000원`), 미국 종목은 달러(`$220.00`) 형식으로 표시합니다.

## 다음 기능 방향

설정 기능은 당분간 `portfolio.json`을 원본으로 유지하고, 웹 UI 또는 Discord 명령이 이 파일을 검증한 뒤 GitHub에 커밋하는 구조로 확장합니다.

## 웹 설정 앱

`web/` 디렉터리에 Next.js 기반 조건 설정 앱이 있습니다. Vercel에 배포할 때는 프로젝트 Root Directory를 `web`으로 지정합니다.

필요한 Vercel 환경변수:

```text
ADMIN_PASSWORD
GITHUB_TOKEN
GITHUB_REPO=gyuwonlee1/KIS_openapi
GITHUB_BRANCH=main
```

웹앱은 관리자 비밀번호로 로그인한 뒤 GitHub API로 `portfolio.json`을 읽고 저장합니다. 저장 전에는 봇과 같은 조건 규칙으로 검증합니다.

웹앱에서 지원하는 작업:

- 종목 추가/수정/삭제
- 종목 활성화/비활성화
- 가격 조건 추가/수정/삭제
- 이동평균선 조건 추가/수정/삭제
- 최초 알림 후 완료 처리 설정
- 재알림 간격 설정

추천 순서:

1. 웹 기반 조건 편집기
2. Discord Slash Command 기반 조건 추가/수정
3. 자연어 조건 설정

자연어 설정은 OpenAI Structured Outputs로 사용자의 문장을 조건 JSON으로 변환하고, 저장 전 사용자 확인을 거치는 방식이 안전합니다.

예시:

```text
삼성전자가 60일 선에 도달하면 알림을 보내줘
```

변환 결과:

```json
{
  "type": "sma_cross",
  "operator": ">=",
  "window": 60
}
```

## 로컬 검증

```powershell
python -m unittest discover -s tests
python -m compileall main.py kis_alert_bot tests
```

이 로컬 환경에서 `python`이 PATH에 없다면 Codex 번들 Python 또는 설치된 Python 경로를 사용합니다.
