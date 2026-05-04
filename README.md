# KIS 주식 알림 봇

한국투자증권(KIS) Open API로 국내/미국 주식 가격을 확인하고, 설정한 조건을 만족하면 Discord로 알림을 보내는 서버리스 주식 알림 봇입니다. GitHub Actions가 15분마다 실행하므로 별도 서버를 계속 켜둘 필요가 없습니다.

## 현재 구현 상태

현재는 단일 관리자용 MVP가 배포되어 있습니다.

- GitHub Actions 15분 주기 실행 및 수동 실행 지원
- KIS 실전투자 REST API 연동
- 국내/미국 현재가 조회
- 국내/미국 일봉 조회
- KIS access token 캐시 재사용
- KIS API 호출 간 최소 0.2초 딜레이
- 조건 평가
  - `price`: 현재가가 목표가 이상/이하일 때
  - `sma_cross`: 현재가가 단순이동평균선 이상/이하일 때
- 시장 시간 필터
  - 국내: 평일 09:00-15:30 KST
  - 미국: 평일 04:00-20:00 America/New_York
- Discord 한국어 Embed 알림
- 오류 요약 Discord 알림
- 1회성 알림 후 조건 자동 삭제
- Vercel 기반 웹 설정 앱
- 웹앱 종목 검색
  - 국내/미국 종목 마스터 JSON 기준
  - 종목명 또는 티커 검색
  - 공백/기호 차이와 주요 한국어 별칭 검색 지원
- 웹앱 조건 설정
  - 가격 조건
  - 20/60/240/480일 이동평균선 조건
- GitHub Actions cache 기반 상태 파일 유지
- Python 및 Next.js 테스트/빌드 CI

## 전체 구조

```text
GitHub Actions Cron
  -> main.py
  -> portfolio.json 로드
  -> KIS API 현재가/일봉 조회
  -> 조건 평가
  -> Discord 알림
  -> 알림 완료 조건을 portfolio.json에서 삭제
```

```text
Vercel 웹앱
  -> GitHub API로 portfolio.json 조회
  -> 종목/조건 편집
  -> GitHub API로 portfolio.json 커밋
```

`portfolio.json`은 현재 조건 설정의 원본입니다. 웹앱의 관심 종목 리스트도 GitHub의 `portfolio.json`을 읽어서 표시합니다.

## 알림 조건

루트의 `portfolio.json`은 아래 형태를 사용합니다.

```json
{
  "stocks": [
    {
      "name": "삼성전자",
      "ticker": "005930",
      "market": "KR",
      "enabled": true,
      "conditions": [
        {
          "id": "price-example",
          "type": "price",
          "operator": ">=",
          "target": 80000,
          "delete_after_alert": true
        }
      ]
    }
  ]
}
```

미국 종목은 `exchange`가 필요합니다.

```json
{
  "name": "Apple Inc.",
  "ticker": "AAPL",
  "market": "US",
  "exchange": "NASD",
  "enabled": true,
  "conditions": [
    {
      "id": "sma-example",
      "type": "sma_cross",
      "operator": "<=",
      "window": 60,
      "delete_after_alert": true
    }
  ]
}
```

조건 필드:

- `type: "price"`: 현재가와 `target` 비교
- `type: "sma_cross"`: 현재가와 `window`일 단순이동평균선 비교
- `operator: ">="`: 이상
- `operator: "<="`: 이하
- `delete_after_alert: true`: 최초 알림 후 조건 완료 처리

웹앱으로 저장하는 조건은 모두 `delete_after_alert: true`로 정규화됩니다. 조건이 실제로 충족되어 Discord 알림이 성공적으로 발송되면 GitHub Actions가 해당 조건을 `portfolio.json`에서 삭제합니다. 같은 종목에 다른 조건이 남아 있으면 종목은 유지되고, 조건이 0개가 된 종목도 관심 종목으로 남을 수 있습니다.

## GitHub Actions 설정

필수 Repository Secrets:

```text
KIS_APP_KEY
KIS_APP_SECRET
DISCORD_WEBHOOK_URL
```

선택 Repository Secret:

```text
KIS_BASE_URL
```

`KIS_BASE_URL`을 비우면 실전투자 OPS 기본 URL을 사용합니다.

스케줄러는 `.github/workflows/scheduler.yml`에 정의되어 있습니다.

- Cron: `*/15 * * * *`
- 수동 실행: `workflow_dispatch`
- 기본 Python: 3.11
- 상태/토큰 캐시: `.cache/kis-alerts`

KIS access token은 `.cache/kis-alerts/kis_token.json`에 저장되고 GitHub Actions cache로 복원됩니다. 토큰 파일은 repository에 커밋하지 않습니다.

## 웹 설정 앱

웹앱은 `web/` 디렉터리의 Next.js 앱입니다. Vercel 배포 시 Root Directory를 `web`으로 설정합니다.

필수 Vercel 환경변수:

```text
ADMIN_PASSWORD
GITHUB_TOKEN
GITHUB_REPO=gyuwonlee1/KIS_openapi
GITHUB_BRANCH=main
```

웹앱 기능:

- 관리자 비밀번호 로그인
- GitHub의 `portfolio.json` 조회
- 국내/미국 종목 검색
- 검증된 종목만 추가
- 종목 활성화/비활성화
- 가격 조건 추가/수정/삭제
- 이동평균선 조건 추가/수정/삭제
- 종목 단위 저장 버튼
- 조건 없는 관심 종목 표시

종목 마스터 데이터는 `web/data/symbols/`의 정적 JSON을 사용합니다. 갱신이 필요하면 아래 명령을 실행합니다.

```powershell
python tools\update_symbol_master.py
```

## Discord 자연어 조건 설정

Discord Slash Command로 자연어 조건을 설정할 수 있습니다.

예시:

```text
/알림 삼성전자가 8만원 이상이면 알려줘
/알림 애플이 60일선 아래로 내려가면 알려줘
```

동작 흐름:

- Discord Interaction Webhook을 Vercel API Route로 수신
- Gemini API Structured Outputs로 자연어를 조건 JSON으로 변환
- 기존 종목 마스터 JSON으로 종목 검증
- 주요 한국어 별칭과 Gemini 티커 힌트로 미국 주식 후보 검색
- 후보가 여러 개이면 Discord 버튼으로 종목 선택
- 저장 전 Discord 버튼으로 사용자 확인
- 확인 시 기존 GitHub API 저장 흐름으로 `portfolio.json` 커밋

필요한 추가 Vercel 환경변수:

```text
DISCORD_PUBLIC_KEY
DISCORD_BOT_TOKEN
DISCORD_APPLICATION_ID
GEMINI_API_KEY
```

선택 환경변수:

```text
DISCORD_GUILD_ID
GEMINI_MODEL=gemini-2.5-flash
```

`DISCORD_GUILD_ID`가 있으면 개발용 guild command로 빠르게 등록하고, 없으면 global command로 등록합니다.

Discord Developer Portal의 Interactions Endpoint URL에는 아래 값을 등록합니다.

```text
https://kis-openapi.vercel.app/api/discord/interactions
```

Slash Command 등록은 Vercel 환경변수와 같은 값을 로컬에도 설정한 뒤 실행합니다.

```powershell
cd web
npm run discord:register
```

## 향후 로드맵

1. 운영 가시성 개선
   - 웹앱에서 마지막 실행 시각 표시
   - 최근 알림 이력 표시
   - 최근 오류 요약 표시

2. Discord 자연어 설정 고도화
   - 종목 후보가 여러 개일 때 선택 버튼 제공
   - 저장된 조건 목록 조회 명령 추가
   - 조건 삭제 명령 추가

3. Supabase 기반 다중 사용자 전환
   - Supabase Auth 도입
   - 사용자별 관심 종목/조건 테이블 생성
   - Row Level Security 적용
   - GitHub `portfolio.json` 대신 Supabase DB를 조건 저장소로 사용
   - 사용자별 Discord 채널 또는 Webhook 연결

## 로컬 검증

Python:

```powershell
python -m unittest discover -s tests
python -m compileall main.py kis_alert_bot tests
```

웹:

```powershell
cd web
npm test
npm run build
```

## 현재 한계

- 단일 관리자/단일 포트폴리오 기준입니다.
- 웹앱 저장은 GitHub commit 기반이라 Supabase 같은 DB 저장 방식보다 느립니다.
- 공휴일, 반장, 임시 휴장 캘린더는 아직 반영하지 않습니다.
- `sma_cross`는 엄밀한 과거 교차 감지가 아니라 현재가와 SMA 기준값 비교입니다.
- 주문 기능은 없고 알림 전용입니다.
