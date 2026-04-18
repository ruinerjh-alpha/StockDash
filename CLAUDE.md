# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**StockBoard** — 개인 투자자용 로컬 주식 관리 대시보드 (Python / Dash).
보유 종목·관심 종목을 카테고리별로 관리하고, 기술 지표 이상 신호를 시각화한다.

## Setup & Run

```bash
cd stockboard
pip install -r ../requirements.txt
python run.py          # 브라우저 자동 오픈 (http://127.0.0.1:8050)
```

`stockboard.db`는 첫 실행 시 `stockboard/` 내에 자동 생성된다.

## Architecture

```
stockboard/
├── run.py            # 진입점: DB 초기화 → 시세 갱신 → Dash 서버 구동
├── app.py            # Dash 앱 객체 + 네비게이션 레이아웃
├── db.py             # SQLite 연결(get_connection) + 테이블 초기화(init_db)
├── models.py         # 테이블별 CRUD + 비즈니스 로직(평단가, 실현손익)
├── data_fetcher.py   # yfinance 래퍼 + 인메모리 캐시(TTL 5분)
├── indicators.py     # RSI·MACD·BB·MA·Volume 계산 + get_signals()
├── assets/style.css  # 다크 테마 커스텀 CSS
└── pages/
    ├── holdings.py   # 보유 종목 (카테고리 탭, 종목 CRUD, 신호 배지)
    ├── watchlist.py  # 관심 종목 (CRUD, 보유 전환)
    ├── detail.py     # 캔들차트 + 지표 오버레이 + 매매 이력 CRUD
    ├── categories.py # 카테고리 CRUD (holding / watchlist 독립)
    ├── settings.py   # 지표 파라미터·임계값 수정, 커스텀 지표 추가
    └── trade_history.py # 전체 매매이력 + FIFO 실현손익
```

### 데이터 흐름

- **DB 스키마**: `categories → stocks → trades`, `watchlist`, `indicator_configs`
- **외래 키**: `stocks.category_id → categories.id`, `trades.stock_id → stocks.id` (CASCADE DELETE)
- **캐시**: `data_fetcher._cache` dict (ticker별 `info_` / `hist_` 키, 5분 TTL)
- **신호 계산**: `indicators.get_signals(df, indicator_configs)` — 활성화된 지표만 순회

### Dash 페이지 패턴

- `use_pages=True` + 각 페이지 상단에 `dash.register_page(__name__, path=...)`
- 콜백은 `@callback` (dash 직접 import) 사용 — app 객체 참조 불필요
- 동적 버튼(수정/삭제)은 패턴 매칭 콜백 `{"type": "...", "index": id}` + `ctx.triggered_id`
- 상태 공유: `dcc.Store` (선택된 ID, 재렌더 트리거 카운터)
- `allow_duplicate=True` — 같은 Output을 여러 콜백이 공유할 때

### 기술 지표 확장

`indicators.py`의 `_check()` 함수에 분기 추가 → `get_signals()`가 자동 호출.
설정 페이지에서 커스텀 지표 추가 시 `indicator_configs` 테이블에 저장되지만,
실제 계산 로직은 `_check()`에 직접 구현해야 한다.

## Key Files

| 목적 | 파일 |
|---|---|
| SQLite 스키마 변경 | `db.py → init_db()` |
| 평단가·손익 계산 로직 | `models.py → calculate_position(), calculate_realized_pnl()` |
| 전체 매매이력 손익 | `models.py → get_all_trades_enriched()` |
| 시세 캐시 TTL 조정 | `data_fetcher.py → CACHE_TTL` |
| 차트 레이아웃 변경 | `pages/detail.py → _build_chart(), _apply_layout()` |
| 지표 임계값 기본값 | `db.py → init_db() defaults` |
