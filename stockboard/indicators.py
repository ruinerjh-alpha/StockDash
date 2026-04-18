"""M4: 기술 지표 계산 (pandas-ta 우선, 폴백 내장)"""
import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
    _HAS_TA = True
except ImportError:
    _HAS_TA = False


# ── 개별 지표 ─────────────────────────────────────────────────────────────────

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    if df.empty or len(df) < period + 1:
        return pd.Series(dtype=float)
    if _HAS_TA:
        r = ta.rsi(df["Close"], length=period)
        return r if r is not None else pd.Series(dtype=float)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta).clip(lower=0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_macd(df: pd.DataFrame, fast: int = 12,
                   slow: int = 26, signal: int = 9) -> pd.DataFrame:
    if df.empty or len(df) < slow + signal:
        return pd.DataFrame()
    if _HAS_TA:
        r = ta.macd(df["Close"], fast=fast, slow=slow, signal=signal)
        if r is not None and not r.empty:
            r.columns = ["MACD", "Histogram", "Signal"]
            return r[["MACD", "Signal", "Histogram"]]
    ema_f = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_s = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_f - ema_s
    sig_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({
        "MACD": macd_line, "Signal": sig_line,
        "Histogram": macd_line - sig_line,
    })


def calculate_bb(df: pd.DataFrame, period: int = 20, std: float = 2) -> pd.DataFrame:
    if df.empty or len(df) < period:
        return pd.DataFrame()
    if _HAS_TA:
        r = ta.bbands(df["Close"], length=period, std=std)
        if r is not None and not r.empty:
            cols = r.columns.tolist()
            l = next((c for c in cols if "BBL" in c), None)
            m = next((c for c in cols if "BBM" in c), None)
            u = next((c for c in cols if "BBU" in c), None)
            if l and m and u:
                return r[[l, m, u]].rename(columns={l: "Lower", m: "Middle", u: "Upper"})
    mid = df["Close"].rolling(period).mean()
    sd = df["Close"].rolling(period).std()
    return pd.DataFrame({"Lower": mid - std * sd, "Middle": mid, "Upper": mid + std * sd})


def calculate_ma(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    if periods is None:
        periods = [5, 20, 60, 120]
    if df.empty:
        return pd.DataFrame()
    return pd.DataFrame({f"MA{p}": df["Close"].rolling(p).mean()
                         for p in periods if len(df) >= p})


# ── 이상 신호 감지 ─────────────────────────────────────────────────────────────

def get_signals(df: pd.DataFrame, configs: list) -> list:
    """활성화된 지표별 이상 신호 리스트 반환"""
    signals = []
    if df.empty or len(df) < 2:
        return signals

    for cfg in configs:
        if not cfg.get("enabled"):
            continue
        ind = cfg["indicator"]
        params = cfg.get("params", {})
        rules = cfg.get("alert_rules", {})
        try:
            _check(ind, df, params, rules, signals)
        except Exception:
            continue
    return signals


def _check(ind, df, params, rules, signals):
    if ind == "RSI":
        rsi = calculate_rsi(df, params.get("period", 14))
        if rsi.empty:
            return
        v = rsi.iloc[-1]
        if pd.isna(v):
            return
        ob = rules.get("overbought", 70)
        os_ = rules.get("oversold", 30)
        if v > ob:
            signals.append({"indicator": "RSI", "signal_type": "overbought",
                             "value": round(v, 1),
                             "description": f"RSI {round(v,1)} > {ob} (과매수)",
                             "color": "danger"})
        elif v < os_:
            signals.append({"indicator": "RSI", "signal_type": "oversold",
                             "value": round(v, 1),
                             "description": f"RSI {round(v,1)} < {os_} (과매도)",
                             "color": "success"})

    elif ind == "MACD":
        mdf = calculate_macd(df, params.get("fast", 12),
                              params.get("slow", 26), params.get("signal", 9))
        if mdf.empty or len(mdf) < 2:
            return
        ph, ch = mdf["Histogram"].iloc[-2], mdf["Histogram"].iloc[-1]
        if pd.isna(ph) or pd.isna(ch):
            return
        if ph < 0 < ch:
            signals.append({"indicator": "MACD", "signal_type": "golden_cross",
                             "value": round(ch, 4), "description": "MACD 골든크로스",
                             "color": "success"})
        elif ph > 0 > ch:
            signals.append({"indicator": "MACD", "signal_type": "dead_cross",
                             "value": round(ch, 4), "description": "MACD 데드크로스",
                             "color": "danger"})

    elif ind == "BB":
        bb = calculate_bb(df, params.get("period", 20), params.get("std", 2))
        if bb.empty:
            return
        close = df["Close"].iloc[-1]
        upper = bb["Upper"].iloc[-1]
        lower = bb["Lower"].iloc[-1]
        if pd.isna(upper) or pd.isna(lower):
            return
        if close > upper:
            signals.append({"indicator": "BB", "signal_type": "upper_breakout",
                             "value": round(close, 2),
                             "description": f"BB 상단 돌파 (≥{round(upper,2)})",
                             "color": "danger"})
        elif close < lower:
            signals.append({"indicator": "BB", "signal_type": "lower_breakout",
                             "value": round(close, 2),
                             "description": f"BB 하단 이탈 (≤{round(lower,2)})",
                             "color": "success"})

    elif ind == "MA":
        periods = params.get("periods", [5, 20, 60, 120])
        ma = calculate_ma(df, periods)
        if ma.empty or len(ma) < 2:
            return
        if "MA5" in ma.columns and "MA20" in ma.columns:
            p5, c5 = ma["MA5"].iloc[-2], ma["MA5"].iloc[-1]
            p20, c20 = ma["MA20"].iloc[-2], ma["MA20"].iloc[-1]
            if not any(pd.isna(x) for x in [p5, c5, p20, c20]):
                if p5 < p20 and c5 > c20:
                    signals.append({"indicator": "MA", "signal_type": "golden_cross",
                                    "value": round(c5, 2), "description": "MA5↑MA20 골든크로스",
                                    "color": "success"})
                elif p5 > p20 and c5 < c20:
                    signals.append({"indicator": "MA", "signal_type": "dead_cross",
                                    "value": round(c5, 2), "description": "MA5↓MA20 데드크로스",
                                    "color": "danger"})

    elif ind == "Volume":
        mp = params.get("ma_period", 5)
        mult = params.get("multiplier", 2)
        if len(df) < mp:
            return
        vol_ma = df["Volume"].rolling(mp).mean().iloc[-1]
        last_vol = df["Volume"].iloc[-1]
        if not pd.isna(vol_ma) and vol_ma > 0 and last_vol > vol_ma * mult:
            signals.append({"indicator": "Volume", "signal_type": "surge",
                             "value": round(last_vol / vol_ma, 1),
                             "description": f"거래량 급증 ({round(last_vol/vol_ma,1)}× 5일 평균)",
                             "color": "warning"})
