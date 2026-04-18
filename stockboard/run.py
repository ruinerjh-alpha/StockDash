"""M9: 진입점 — python run.py → 브라우저 자동 실행"""
import sys
import os
import threading
import webbrowser
import time

# stockboard/ 를 sys.path 최상단에 추가 (pages/ 내 import 지원)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import init_db
import models
import data_fetcher
from app import app

# pages 자동 등록 (use_pages=True 가 자동 처리하나 명시적 import 로 보장)
import pages.holdings      # noqa: F401
import pages.watchlist     # noqa: F401
import pages.detail        # noqa: F401
import pages.categories    # noqa: F401
import pages.settings      # noqa: F401
import pages.trade_history # noqa: F401


def _open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8050")


def _refresh_on_start():
    """앱 시작 시 KRX 인덱스 로드 + 보유·관심 종목 시세 갱신"""
    try:
        print("[StockBoard] KRX 종목 인덱스 로드 중...")
        data_fetcher._ensure_krx_index()
    except Exception as e:
        print(f"[StockBoard] KRX 인덱스 로드 실패: {e}")
    try:
        tickers = [s["ticker"] for s in models.get_stocks()]
        tickers += [w["ticker"] for w in models.get_watchlist()]
        tickers = list(set(tickers))
        if tickers:
            print(f"[StockBoard] 시세 갱신 중: {tickers}")
            data_fetcher.refresh_all(tickers)
            print("[StockBoard] 시세 갱신 완료")
    except Exception as e:
        print(f"[StockBoard] 시세 갱신 실패: {e}")


if __name__ == "__main__":
    print("[StockBoard] DB 초기화 중...")
    init_db()
    print("[StockBoard] DB 초기화 완료")

    threading.Thread(target=_refresh_on_start, daemon=True).start()
    threading.Thread(target=_open_browser, daemon=True).start()

    print("[StockBoard] http://127.0.0.1:8050 에서 실행 중")
    app.run(debug=False, host="127.0.0.1", port=8050)
