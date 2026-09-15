import pyupbit
import pandas as pd
import numpy as np
import asyncio
from indicators import calculate_rsi, calculate_macd, calculate_ma, calculate_atr
import json
import os
from config import config

FEE = 0.0005
SLIPPAGE = 0.0005
RISK_PER_TRADE = 0.01
STATE_FILE = config.STATE_PATH

def simulate_strategy(df: pd.DataFrame, sl_coef: float, trail_start: float, trail_drop: float) -> dict:
    capital = 1000000.0
    position = 0.0
    entry_price = 0.0
    entry_atr = 0.0
    highest_price = 0.0
    
    winning_trades = []
    losing_trades = []
    
    cooldown_until = None
    consecutive_losses = 0
    
    for i in range(100, len(df)-1):
        idx = df.index[i]
        row = df.loc[idx]
        
        if cooldown_until and idx < cooldown_until: continue
        
        if position > 0:
            curr_high, curr_low, curr_close = row['high'], row['low'], row['close']
            if curr_high > highest_price: highest_price = curr_high
                
            trailing_sl_price = entry_price - (sl_coef * entry_atr)
            
            if highest_price >= entry_price + (trail_start * entry_atr):
                trailing_sl_price = highest_price - (trail_drop * entry_atr)
                
            if curr_low <= trailing_sl_price:
                exit_price = trailing_sl_price * (1 - SLIPPAGE)
                revenue = position * exit_price * (1 - FEE)
                profit = revenue - (position * entry_price)
                capital += profit
                
                if profit > 0:
                    winning_trades.append(profit)
                    consecutive_losses = 0
                else:
                    losing_trades.append(profit)
                    consecutive_losses += 1
                    cooldown_until = idx + pd.Timedelta(hours=2)
                    if consecutive_losses >= 3:
                        cooldown_until = idx + pd.Timedelta(hours=24)
                        
                position = 0.0
                continue
                
        if position == 0:
            buy_signal = False
            rsi = row['rsi_14']
            macd_hist = row['macd_hist']
            macd_sig = row['macd_sig']
            macd_golden = row['macd_val'] > row['macd_sig']
            regime = row['regime']
            
            if rsi < 40 and macd_hist > 0: buy_signal = True
            elif regime == "AGGRESSIVE" and macd_golden and rsi < 65: buy_signal = True
                
            if buy_signal:
                next_open = df.iloc[i+1]['open']
                entry_price = next_open * (1 + SLIPPAGE)
                entry_atr = row['atr_14']
                
                stop_loss_pct = (sl_coef * entry_atr) / entry_price
                if stop_loss_pct > 0:
                    target_krw = min((capital * RISK_PER_TRADE) / stop_loss_pct, capital)
                    target_krw *= (1 - FEE)
                    position = target_krw / entry_price
                    capital -= target_krw
                    highest_price = entry_price

    gross_profit = sum(winning_trades)
    gross_loss = abs(sum(losing_trades))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    
    return {
        "pf": profit_factor,
        "win_rate": len(winning_trades) / (len(winning_trades) + len(losing_trades)) * 100 if (winning_trades or losing_trades) else 0.0,
        "total_trades": len(winning_trades) + len(losing_trades)
    }

async def run_auto_optimization():
    """백그라운드에서 최근 30일 데이터를 통해 최적의 ATR 파라미터를 찾고 상태를 업데이트합니다."""
    print("🔄 [Auto-Tuning] 자가 학습 및 파라미터 최적화를 시작합니다...")
    
    try:
        df = pyupbit.get_ohlcv("KRW-XRP", interval="minute15", count=2880) # 약 30일
        if df is None or df.empty:
            print("데이터 수집 실패로 최적화를 중단합니다.")
            return

        # 지표 계산
        for col in ['rsi_14', 'macd_hist', 'macd_val', 'macd_sig', 'atr_14', 'ma5', 'ma20', 'ma60']: df[col] = 0.0
        df['regime'] = "NONE"

        # 지표 일괄 계산 (단순화된 루프)
        for i in range(100, len(df)):
            window = df.iloc[i-100:i+1]
            macd = calculate_macd(window)
            ma = calculate_ma(window)
            df.loc[df.index[i], 'rsi_14'] = calculate_rsi(window)
            df.loc[df.index[i], 'macd_hist'] = macd['histogram']
            df.loc[df.index[i], 'macd_val'] = macd['macd']
            df.loc[df.index[i], 'macd_sig'] = macd['signal']
            df.loc[df.index[i], 'atr_14'] = calculate_atr(window)
            
            if ma['ma5'] > ma['ma20'] > ma['ma60'] and macd['histogram'] > 0: df.loc[df.index[i], 'regime'] = "AGGRESSIVE"
            elif ma['ma5'] < ma['ma20'] < ma['ma60'] and macd['histogram'] < 0: df.loc[df.index[i], 'regime'] = "DEFENSIVE"
            else: df.loc[df.index[i], 'regime'] = "BALANCED"

        # 파라미터 조합 (Grid Search)
        best_pf = 0.0
        best_params = {"sl": 1.5, "ts": 1.5, "td": 0.75}

        sl_opts = [1.5, 2.0, 2.5]
        ts_opts = [1.5, 2.0, 2.5]
        td_opts = [0.5, 0.75, 1.0]

        for sl in sl_opts:
            for ts in ts_opts:
                for td in td_opts:
                    res = simulate_strategy(df, sl, ts, td)
                    # 최소 거래 횟수 방어 로직 (최소 5번은 거래해야 유의미함)
                    if res["total_trades"] >= 5 and res["pf"] > best_pf:
                        best_pf = res["pf"]
                        best_params = {"sl": sl, "ts": ts, "td": td, "pf": res["pf"], "wr": res["win_rate"]}

        print(f"✅ [Auto-Tuning 완료] 최적 파라미터 발견: 손절 {best_params['sl']} ATR, 익절시작 {best_params['ts']} ATR, 익절추적 {best_params['td']} ATR (예상 PF: {best_params.get('pf',0):.2f})")

        # 상태 파일 업데이트
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        else:
            state = {}

        state["optim_stop_loss"] = best_params["sl"]
        state["optim_trailing_start"] = best_params["ts"]
        state["optim_trailing_drop"] = best_params["td"]
        
        # 튜닝 성공 기록
        import time
        state["last_tuning_time"] = time.time()

        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
            
        from telegram_notifier import send_telegram_message
        send_telegram_message(f"🧠 *[AI 자가 학습 완료]*\n최근 장세에 맞춰 알고리즘이 뇌 구조를 업데이트했습니다.\n• 손절: `{best_params['sl']}` ATR\n• 트레일링 시작: `{best_params['ts']}` ATR\n• 트레일링 폭: `{best_params['td']}` ATR\n• 가상 팩터(PF): `{best_params.get('pf',0):.2f}`\n\n다음 매매부터 새 파라미터가 적용됩니다.")

    except Exception as e:
        print(f"❌ Auto-Tuning 중 오류 발생: {e}")
