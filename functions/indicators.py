import pandas as pd
import numpy as np

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """Wilder's Smoothed RSI 정밀 계산"""
    if len(df) < period + 1:
        return 50.0

    delta = df['close'].diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # 초기 SMA로 시작
    avg_gain = gain.iloc[:period].mean()
    avg_loss = loss.iloc[:period].mean()

    # Wilder's EMA (smoothed) 방식 적용
    for i in range(period, len(delta)):
        avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / (avg_loss + 1e-10)
    return float(100 - (100 / (1 + rs)))

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD 계산 (1시간봉 기준 표준 파라미터)"""
    if len(df) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return {
        "macd": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "histogram": float(histogram.iloc[-1])
    }

def calculate_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> dict:
    """볼린저 밴드 계산 및 %B 위치 반환"""
    if len(df) < window:
        close_val = float(df['close'].iloc[-1]) if not df.empty else 0.0
        return {"upper": close_val, "mid": close_val, "lower": close_val, "bandwidth": 0.0}

    rolling_mean = df['close'].rolling(window=window).mean()
    rolling_std = df['close'].rolling(window=window).std()
    upper = rolling_mean + (rolling_std * num_std)
    lower = rolling_mean - (rolling_std * num_std)
    mid = rolling_mean.iloc[-1]
    u = float(upper.iloc[-1])
    l = float(lower.iloc[-1])
    bandwidth = ((u - l) / mid * 100) if mid > 0 else 0.0

    return {"upper": u, "mid": float(mid), "lower": l, "bandwidth": round(bandwidth, 2)}

def calculate_ma(df: pd.DataFrame) -> dict:
    """이동평균선 계산 (MA5, MA20, MA60, MA120)"""
    if df.empty:
        return {"ma5": 0.0, "ma20": 0.0, "ma60": 0.0, "ma120": 0.0}

    close = df['close']
    def safe_ma(w): 
        return float(close.rolling(window=w).mean().iloc[-1]) if len(close) >= w else float(close.iloc[-1])

    return {
        "ma5": safe_ma(5),
        "ma20": safe_ma(20),
        "ma60": safe_ma(60),
        "ma120": safe_ma(120)
    }

def calculate_volume_trend(df: pd.DataFrame) -> dict:
    """최근 거래량 추세 분석 (거래량 급증 = 강한 추세 신호)"""
    if len(df) < 10:
        return {"vol_ratio": 1.0, "is_volume_spike": False}
    recent_vol = df['volume'].iloc[-1]
    avg_vol = df['volume'].iloc[-10:].mean()
    ratio = recent_vol / (avg_vol + 1e-10)
    return {
        "vol_ratio": round(float(ratio), 2),
        "is_volume_spike": bool(ratio > 1.8)  # 최근 평균 대비 1.8배 이상이면 급증
    }

def get_all_indicators(df: pd.DataFrame) -> dict:
    """모든 기술적 지표를 통합하여 반환"""
    if df.empty or 'close' not in df:
        return {}

    return {
        "rsi_14": calculate_rsi(df),
        "macd": calculate_macd(df),
        "bollinger": calculate_bollinger_bands(df),
        "ma": calculate_ma(df),
        "volume_trend": calculate_volume_trend(df),
        "current_price": float(df['close'].iloc[-1])
    }
