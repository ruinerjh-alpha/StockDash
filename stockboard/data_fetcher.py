"""M3: yfinance 시세 수집 + 인메모리 캐싱 (안정화 버전)"""
import time
import threading
import requests
import pandas as pd
import yfinance as yf

_cache: dict = {}
_lock = threading.Lock()
CACHE_TTL = 300  # 5분

# ── 국내 주요 종목 로컬 테이블 (API 불필요 — 한글 검색 1차 소스) ───────────────
KR_STOCK_NAMES: dict[str, str] = {
    # KOSPI 대형주
    "005930.KS": "삼성전자",
    "005935.KS": "삼성전자우",
    "000660.KS": "SK하이닉스",
    "207940.KS": "삼성바이오로직스",
    "005380.KS": "현대차",
    "005385.KS": "현대차우",
    "000270.KS": "기아",
    "051910.KS": "LG화학",
    "006400.KS": "삼성SDI",
    "373220.KS": "LG에너지솔루션",
    "035420.KS": "NAVER",
    "035720.KS": "카카오",
    "105560.KS": "KB금융",
    "055550.KS": "신한지주",
    "086790.KS": "하나금융지주",
    "316140.KS": "우리금융지주",
    "066570.KS": "LG전자",
    "003550.KS": "LG",
    "034730.KS": "SK",
    "017670.KS": "SK텔레콤",
    "030200.KS": "KT",
    "012330.KS": "현대모비스",
    "028260.KS": "삼성물산",
    "096770.KS": "SK이노베이션",
    "018260.KS": "삼성에스디에스",
    "009150.KS": "삼성전기",
    "032830.KS": "삼성생명",
    "000810.KS": "삼성화재",
    "003490.KS": "대한항공",
    "011200.KS": "HMM",
    "090430.KS": "아모레퍼시픽",
    "010950.KS": "S-Oil",
    "000100.KS": "유한양행",
    "251270.KS": "넷마블",
    "000720.KS": "현대건설",
    "011790.KS": "SKC",
    "010130.KS": "고려아연",
    "000080.KS": "하이트진로",
    "021240.KS": "코웨이",
    "018880.KS": "한온시스템",
    "009540.KS": "한국조선해양",
    "010140.KS": "삼성중공업",
    "042660.KS": "한화오션",
    "047050.KS": "포스코인터내셔널",
    "005490.KS": "POSCO홀딩스",
    "003670.KS": "포스코퓨처엠",
    "000150.KS": "두산",
    "042670.KS": "HD현대인프라코어",
    "329180.KS": "HD현대중공업",
    "267250.KS": "HD현대",
    "000040.KS": "KYK",
    "032640.KS": "LG유플러스",
    "033780.KS": "KT&G",
    "004020.KS": "현대제철",
    "005850.KS": "에스엘",
    "007070.KS": "GS리테일",
    "078930.KS": "GS",
    "071050.KS": "한국금융지주",
    "139480.KS": "이마트",
    "004170.KS": "신세계",
    "023530.KS": "롯데쇼핑",
    "011170.KS": "롯데케미칼",
    "004990.KS": "롯데지주",
    "002790.KS": "아모레G",
    "011780.KS": "금호석유",
    "003000.KS": "부광약품",
    "000070.KS": "삼양홀딩스",
    "002380.KS": "KCC",
    "000210.KS": "DL",
    "006360.KS": "GS건설",
    "028050.KS": "삼성엔지니어링",
    "000120.KS": "CJ대한통운",
    "097950.KS": "CJ제일제당",
    "001040.KS": "CJ",
    "010060.KS": "OCI홀딩스",
    "003240.KS": "태광산업",
    "010620.KS": "현대미포조선",
    "000880.KS": "한화",
    "012450.KS": "한화에어로스페이스",
    "064350.KS": "한화생명",
    "082740.KS": "한화솔루션",
    "009830.KS": "한화갤러리아",
    # KOSDAQ 주요주
    "068270.KQ": "셀트리온",
    "263750.KQ": "펄어비스",
    "293490.KQ": "카카오게임즈",
    "035900.KQ": "JYP Ent.",
    "041510.KQ": "에스엠",
    "122870.KQ": "와이지엔터테인먼트",
    "247540.KQ": "에코프로비엠",
    "086520.KQ": "에코프로",
    "357780.KQ": "솔브레인",
    "145020.KQ": "휴젤",
    "196170.KQ": "알테오젠",
    "091990.KQ": "셀트리온헬스케어",
    "214150.KQ": "클래시스",
    "112040.KQ": "위메이드",
    "095340.KQ": "ISC",
    "039030.KQ": "이오테크닉스",
    "028300.KQ": "HLB",
    "323410.KQ": "카카오뱅크",
    "377300.KQ": "카카오페이",
}


# ── 캐시 헬퍼 ─────────────────────────────────────────────────────────────────

def _valid(key: str) -> bool:
    if key not in _cache:
        return False
    _, ts = _cache[key]
    return (time.time() - ts) < CACHE_TTL


def _store(key: str, value):
    with _lock:
        _cache[key] = (value, time.time())


def _load(key: str):
    with _lock:
        return _cache[key][0] if key in _cache else None


# ── 티커 정규화 ───────────────────────────────────────────────────────────────

def normalize_ticker(ticker: str) -> str:
    """
    입력 티커를 Yahoo Finance 형식으로 정규화.
    - 6자리 숫자 → 임시 .KS 부착 (resolve_krx_ticker로 KQ 판별 가능)
    - 이미 접미사(.KS/.KQ 등) 있으면 대문자만 변환
    - 알파벳(US 주식)은 그대로 대문자 반환
    """
    t = ticker.strip().upper()
    if not t:
        return t
    if "." in t:
        return t
    digits = t.lstrip("0") and t  # 보존용
    if t.isdigit():
        return t.zfill(6) + ".KS"   # 임시 — 선택 시 resolve_krx_ticker 사용
    return t


# ── 안정적 시세 조회 ──────────────────────────────────────────────────────────

def get_stock_info(ticker: str, retries: int = 3) -> dict:
    """
    현재가·종목명·등락률 반환.
    fast_info 우선 → info 폴백, 최대 retries 회 재시도.
    오프라인이면 캐시 데이터 반환.
    """
    key = f"info_{ticker}"
    with _lock:
        if _valid(key):
            return _cache[key][0]

    last_err = None
    for attempt in range(retries):
        try:
            stock = yf.Ticker(ticker)
            fast = stock.fast_info

            price = getattr(fast, "last_price", None) or 0
            prev  = getattr(fast, "previous_close", None) or 0

            # fast_info 가격이 없으면 info로 폴백
            if not price:
                info  = stock.info
                price = (info.get("regularMarketPrice")
                         or info.get("currentPrice") or 0)
                prev  = info.get("previousClose") or 0
                name_raw = (info.get("longName")
                            or info.get("shortName") or ticker)
            else:
                # 이름: KR_STOCK_NAMES 테이블 우선
                name_raw = KR_STOCK_NAMES.get(ticker)
                if not name_raw:
                    try:
                        info = stock.info
                        name_raw = (info.get("longName")
                                    or info.get("shortName") or ticker)
                    except Exception:
                        name_raw = ticker

            price = float(price or 0)
            prev  = float(prev  or 0)
            change_pct = ((price - prev) / prev * 100) if prev else 0.0

            result = {
                "ticker":        ticker,
                "name":          KR_STOCK_NAMES.get(ticker, name_raw),
                "current_price": round(price, 4),
                "prev_close":    round(prev, 4),
                "change_pct":    round(change_pct, 2),
                "online":        True,
            }
            _store(key, result)
            return result

        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))

    # 재시도 모두 실패
    cached = _load(key)
    if cached:
        d = dict(cached)
        d["online"] = False
        return d
    return {
        "ticker": ticker,
        "name":   KR_STOCK_NAMES.get(ticker, ticker),
        "current_price": 0, "prev_close": 0,
        "change_pct": 0, "online": False,
        "error": str(last_err),
    }


def get_stock_name(ticker: str) -> str:
    """종목명만 빠르게 반환 (KR_STOCK_NAMES 우선)."""
    if ticker in KR_STOCK_NAMES:
        return KR_STOCK_NAMES[ticker]
    try:
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName") or ticker
    except Exception:
        return ticker


# ── 안정적 시계열 조회 ────────────────────────────────────────────────────────

def get_historical_data(ticker: str, period: str = "6mo",
                        retries: int = 3) -> pd.DataFrame:
    """OHLCV DataFrame 반환. 재시도 3회, 오프라인 시 캐시 반환."""
    key = f"hist_{ticker}_{period}"
    with _lock:
        if _valid(key):
            return _cache[key][0]

    for attempt in range(retries):
        try:
            df = yf.Ticker(ticker).history(period=period)
            if not df.empty:
                df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
                df.index = pd.to_datetime(df.index)
                _store(key, df)
                return df
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(0.5 * (attempt + 1))

    cached = _load(key)
    return cached if cached is not None else pd.DataFrame()


# ── KRX 티커 판별 ─────────────────────────────────────────────────────────────

def resolve_krx_ticker(code: str) -> tuple:
    """
    6자리 KRX 종목코드로 .KS/.KQ 자동 판별.
    KR_STOCK_NAMES 사전 우선 확인 → 실제 가격 조회.
    반환: (resolved_ticker, price_info_dict)
    """
    code = code.strip().zfill(6)

    # 사전에서 먼저 확인
    for suffix in (".KS", ".KQ"):
        candidate = f"{code}{suffix}"
        if candidate in KR_STOCK_NAMES:
            return candidate, get_stock_info(candidate)

    # 실제 가격 조회로 판별
    for suffix in (".KS", ".KQ"):
        ticker = f"{code}{suffix}"
        info = get_stock_info(ticker)
        if info.get("current_price", 0) > 0:
            return ticker, info

    # 모두 실패 → KS 기본값
    fallback = f"{code}.KS"
    return fallback, get_stock_info(fallback)


# ── 캐시 관리 ─────────────────────────────────────────────────────────────────

def invalidate(ticker: str):
    """특정 종목 캐시 삭제 (수동 새로고침용)."""
    with _lock:
        for key in [k for k in list(_cache) if ticker in k]:
            del _cache[key]


def refresh_all(tickers: list):
    """앱 시작 시 전체 종목 시세 갱신."""
    for ticker in tickers:
        invalidate(ticker)
        get_stock_info(ticker)


def get_batch_info(tickers: list) -> dict:
    return {t: get_stock_info(t) for t in tickers}


# ── KRX 전체 종목 인덱스 (FinanceDataReader, 24시간 캐시) ────────────────────

_krx_index: dict = {}          # code → {"name", "market", "ticker"}
_krx_index_ts: float = 0.0
_KRX_TTL = 86400               # 24시간


def _ensure_krx_index():
    """KRX 전체 종목 목록을 로드해 _krx_index에 저장. 24시간 캐시."""
    global _krx_index, _krx_index_ts
    if _krx_index and (time.time() - _krx_index_ts) < _KRX_TTL:
        return
    try:
        import FinanceDataReader as fdr
        df = fdr.StockListing("KRX")
        idx = {}
        for _, row in df.iterrows():
            code = str(row.get("Code", "")).zfill(6)
            name = str(row.get("Name", "")).strip()
            market = str(row.get("Market", "")).upper()
            if not code or not name:
                continue
            suffix = ".KQ" if "KOSDAQ" in market else ".KS"
            # KR_STOCK_NAMES의 이름이 더 정확할 수 있으므로 우선 적용
            kr_name = KR_STOCK_NAMES.get(f"{code}{suffix}", name)
            idx[code] = {"name": kr_name, "market": market, "ticker": f"{code}{suffix}"}
        _krx_index = idx
        _krx_index_ts = time.time()
        print(f"[StockBoard] KRX 종목 인덱스 로드 완료: {len(idx)}종목")
    except Exception as e:
        print(f"[StockBoard] KRX 인덱스 로드 실패: {e}")
        # 폴백: KR_STOCK_NAMES를 인덱스로 사용
        if not _krx_index:
            for ticker, name in KR_STOCK_NAMES.items():
                code = ticker.split(".")[0]
                market = "KOSDAQ" if ticker.endswith(".KQ") else "KOSPI"
                _krx_index[code] = {"name": name, "market": market, "ticker": ticker}


# ── 종목 검색 ─────────────────────────────────────────────────────────────────

def _has_korean(text: str) -> bool:
    return any('\uAC00' <= c <= '\uD7A3' for c in text)


def _search_kr(query: str) -> list:
    """KRX 전체 종목 인덱스에서 한글 이름/코드 부분 일치 검색."""
    _ensure_krx_index()
    q = query.strip().lower()
    results = []
    for code, info in _krx_index.items():
        name = info["name"]
        if q in name.lower() or q in code:
            results.append({
                "ticker":   info["ticker"],
                "name":     name,
                "exchange": "KQ" if info["ticker"].endswith(".KQ") else "KS",
                "type":     "주식",
                "_src":     "local",
                "_code":    code,
            })
        if len(results) >= 20:
            break
    return results


def _search_yahoo(query: str) -> list:
    """Yahoo Finance 검색 — 영문·티커 검색에 적합."""
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        params = {
            "q": query.strip(),
            "quotesCount": 10,
            "newsCount": 0,
            "enableFuzzyQuery": True,
            "lang": "ko-KR",
            "region": "KR",
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        resp.raise_for_status()
        results = []
        for q in resp.json().get("quotes", []):
            sym = q.get("symbol")
            if not sym:
                continue
            results.append({
                "ticker":   sym,
                "name":     (q.get("longname") or q.get("shortname") or sym),
                "exchange": q.get("exchDisp") or q.get("exchange") or "",
                "type":     q.get("typeDisp") or q.get("quoteType") or "",
                "_src":     "yahoo",
            })
        return results
    except Exception:
        return []


def search_tickers(query: str) -> list:
    """
    검색 우선순위:
      한글 → KRX 전체 인덱스(즉시) → Yahoo 보완
      영문/티커 → Yahoo → 6자리 숫자면 KRX 인덱스
    최대 10건 반환.
    """
    if not query or not query.strip():
        return []

    seen: set = set()
    results: list = []

    def _add(items):
        for r in items:
            key = r.get("_code") or r["ticker"]
            if key not in seen:
                seen.add(key)
                results.append(r)

    if _has_korean(query):
        _add(_search_kr(query))        # ① KRX 전체 인덱스 (2,800+ 종목)
        _add(_search_yahoo(query))     # ② Yahoo 보완
    else:
        _add(_search_yahoo(query))     # ① Yahoo
        q = query.strip()
        if q.isdigit():                # ② 6자리 숫자 직접 입력
            _ensure_krx_index()
            code = q.zfill(6)
            if code not in seen and code in _krx_index:
                seen.add(code)
                info = _krx_index[code]
                results.append({
                    "ticker":   info["ticker"],
                    "name":     info["name"],
                    "exchange": "KQ" if info["ticker"].endswith(".KQ") else "KS",
                    "type":     "주식",
                    "_src":     "local", "_code": code,
                })

    return results[:10]
