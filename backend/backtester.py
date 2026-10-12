"""돌파 추세추종 전략 백테스터 (실거래 로직과 동일한 config 파라미터 사용)

사용법: python backtester.py [캔들 수, 기본 17000 ≈ 2년치 1시간봉]
- 마감된 봉에서 신호 판단 → 다음 봉 시가에 체결
- 손절선 = max(진입가 - ATR_STOP_MULT*ATR, 보유 중 최고가 - ATR_TRAIL_MULT*ATR)
- 종가가 EMA 아래로 마감하면 다음 봉 시가에 청산
- 거래소 안전 예약 매도(+10%) 체결 반영
- 편도 비용 0.1% (수수료 0.05% + 슬리피지 0.05%)
"""
import sys
import pyupbit
import pandas as pd
import numpy as np
from config import config

COST = 0.001
SAFETY_TP = 0.10
START_CAPITAL = 1_000_000.0

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    prev_close = df['close'].shift()
    tr = pd.concat([df['high'] - df['low'], (df['high'] - prev_close).abs(), (df['low'] - prev_close).abs()], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    df['ema'] = df['close'].ewm(span=config.TREND_EMA_PERIOD, adjust=False).mean()
    df['breakout_high'] = df['high'].shift(1).rolling(config.BREAKOUT_PERIOD).max()
    df['entry_sig'] = (df['close'] > df['breakout_high']) & (df['close'] > df['ema'])
    df['exit_sig'] = df['close'] < df['ema']
    return df

def simulate(df: pd.DataFrame) -> dict:
    o, h, l, c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    atr, ent, ext = df['atr'].values, df['entry_sig'].values, df['exit_sig'].values
    cash, qty = START_CAPITAL, 0.0
    entry = entry_atr = highest = 0.0
    trades, equity = [], np.empty(len(df))

    def close_position(px):
        nonlocal cash, qty
        cash += qty * px * (1 - COST)
        trades.append(px / entry - 1 - 2 * COST)
        qty = 0.0

    for i in range(config.TREND_EMA_PERIOD, len(df)):
        if qty > 0:
            stop = max(entry - config.ATR_STOP_MULT * entry_atr, highest - config.ATR_TRAIL_MULT * entry_atr)
            if h[i] >= entry * (1 + SAFETY_TP) and o[i] < entry * (1 + SAFETY_TP):
                close_position(entry * (1 + SAFETY_TP))
            elif l[i] <= stop:
                close_position(min(o[i], stop))
            elif ext[i - 1]:
                close_position(o[i])
            else:
                highest = max(highest, h[i])
        if qty == 0 and ent[i - 1]:
            entry, entry_atr, highest = o[i], atr[i - 1], o[i]
            stop_pct = config.ATR_STOP_MULT * entry_atr / entry
            invest = min(cash * config.RISK_PER_TRADE_PCT / 100 / stop_pct, cash)
            qty = invest * (1 - COST) / entry
            cash -= invest
            if l[i] <= entry - config.ATR_STOP_MULT * entry_atr:
                close_position(entry - config.ATR_STOP_MULT * entry_atr)
            else:
                highest = max(highest, h[i])
        equity[i] = cash + qty * c[i]

    equity = pd.Series(equity[config.TREND_EMA_PERIOD:], index=df.index[config.TREND_EMA_PERIOD:])
    r = np.array(trades)
    gross_win, gross_loss = r[r > 0].sum(), -r[r < 0].sum()
    return {
        "equity": equity,
        "trades": len(r),
        "win_rate": (r > 0).mean() * 100 if len(r) else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else float('inf'),
        "avg_win": r[r > 0].mean() * 100 if (r > 0).any() else 0.0,
        "avg_loss": r[r < 0].mean() * 100 if (r < 0).any() else 0.0,
        "return_pct": (equity.iloc[-1] / START_CAPITAL - 1) * 100,
        "max_drawdown": (equity / equity.cummax() - 1).min() * 100,
    }

def run_backtest(count: int = 17000):
    print(f"XRP/KRW {config.STRATEGY_INTERVAL} {count}개 캔들 수집 중...")
    df = pyupbit.get_ohlcv("KRW-XRP", interval=config.STRATEGY_INTERVAL, count=count)
    if df is None or df.empty:
        print("데이터 수집 실패")
        return
    df = add_indicators(df.iloc[:-1])  # 진행 중인 봉 제외
    res = simulate(df)
    eq = res["equity"]
    buy_hold = (df['close'].iloc[-1] / df['close'].iloc[config.TREND_EMA_PERIOD] - 1) * 100

    print(f"\n=== 백테스트 결과 ({eq.index[0]} ~ {eq.index[-1]}) ===")
    print(f"파라미터: 돌파 {config.BREAKOUT_PERIOD}봉 / EMA{config.TREND_EMA_PERIOD} / 손절 {config.ATR_STOP_MULT}ATR / 트레일링 {config.ATR_TRAIL_MULT}ATR / 리스크 {config.RISK_PER_TRADE_PCT}%")
    print(f"총 거래: {res['trades']}회 | 승률 {res['win_rate']:.1f}% | PF {res['profit_factor']:.2f}")
    print(f"평균 익절 {res['avg_win']:+.2f}% / 평균 손절 {res['avg_loss']:+.2f}%")
    print(f"수익률 {res['return_pct']:+.1f}% (단순 보유 {buy_hold:+.1f}%) | 최대 낙폭 {res['max_drawdown']:.1f}%")
    print("\n분기별 수익률:")
    q = eq.resample('QE').last()
    prev = START_CAPITAL
    for t, v in q.items():
        print(f"  {t.year}Q{t.quarter}: {(v / prev - 1) * 100:+.1f}%")
        prev = v

if __name__ == "__main__":
    run_backtest(int(sys.argv[1]) if len(sys.argv) > 1 else 17000)
