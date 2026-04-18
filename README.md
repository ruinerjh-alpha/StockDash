# StockBoard

개인 투자자용 로컬 주식 관리 대시보드 (Python / Dash)

## 주요 기능

- **보유 종목 관리** — 카테고리 탭, 매수/매도 거래 입력, 기술지표 이상 신호 배지
- **관심 종목 관리** — 등록가 대비 등락 추적, 보유 종목 전환
- **매매이력** — 전체 거래 내역 조회, FIFO 기반 실현손익·수익률 자동 계산
- **종목 상세** — 캔들차트 + MA/BB/MACD/Volume 오버레이, 매매 이력 CRUD
- **카테고리 관리** — 보유/관심 독립 카테고리, 색상 지정
- **지표 설정** — 파라미터·임계값 수정, 커스텀 지표 추가
- **KRX 전체 종목 검색** — FinanceDataReader 기반 2,800+ 종목 한글 검색

## 설치 및 실행

```bash
git clone https://github.com/ruinerjh-alpha/StockDash.git
cd StockDash
pip install -r requirements.txt
cd stockboard
python run.py
```

브라우저가 자동으로 `http://127.0.0.1:8050` 을 엽니다.  
SQLite DB (`stockboard.db`)는 첫 실행 시 자동 생성됩니다.

## 기술 스택

| 구분 | 라이브러리 |
|---|---|
| UI 프레임워크 | Dash 2.x + dash-bootstrap-components |
| 차트 | Plotly |
| 시세 수집 | yfinance, FinanceDataReader |
| 기술 지표 | pandas-ta (폴백: 내장 계산) |
| DB | SQLite (내장) |

## 프로젝트 구조

```
stockboard/
├── run.py            # 진입점
├── app.py            # Dash 앱 + 네비게이션
├── db.py             # SQLite 스키마
├── models.py         # CRUD + 손익 계산
├── data_fetcher.py   # 시세 수집 + KRX 검색
├── indicators.py     # RSI·MACD·BB·MA·Volume
├── assets/style.css  # 다크 테마
└── pages/
    ├── holdings.py
    ├── watchlist.py
    ├── detail.py
    ├── categories.py
    ├── settings.py
    └── trade_history.py
```
