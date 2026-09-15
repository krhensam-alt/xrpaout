import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from indicators import calculate_rsi, calculate_macd, calculate_bollinger_bands, calculate_ma, calculate_atr

# --- 설정값 ---
FEE = 0.0005        # 편도 수수료 0.05%
SLIPPAGE = 0.0005   # 편도 슬리피지 0.05%
TOTAL_COST = (FEE + SLIPPAGE) * 2  # 왕복 0.2%

ATR_STOP_LOSS = 1.5
ATR_PROFIT_LOCK = 3.0
ATR_PROFIT_LOCK_RAISE = 1.0
ATR_TRAILING_START = 1.5
ATR_TRAILING_DROP = 0.75

START_CAPITAL = 1000000.0
RISK_PER_TRADE = 0.01  # 자본의 1% 리스크

def run_backtest(days_back=365):
    print(f"XRP/KRW 15분봉 과거 {days_back}일 데이터 수집 중...")
    
    # 데이터 수집 (200개씩 페이징)
    df = pd.DataFrame()
    to_date = datetime.now()
    
    # 15분봉 기준 하루 = 96개. 365일 = 35040개. 200개씩 = 175번 요청
    # 너무 오래 걸리므로 최근 6개월(180일) 정도로 타협
    target_candles = days_back * 96
    
    # 속도를 위해 우선 최근 4000 캔들(약 40일)만 로드해봅니다 (API 제한 고려)
    # 실제 프로덕션 검증 시에는 로컬 DB에 데이터를 적재해서 해야함.
    df = pyupbit.get_ohlcv("KRW-XRP", interval="minute15", count=4000)
    
    if df is None or df.empty:
        print("데이터 수집 실패")
        return
        
    print(f"총 {len(df)}개 캔들 데이터 수집 완료. 백테스트 시작...")
    
    # 벡터화 연산을 위한 지표 미리 계산
    df['rsi_14'] = calculate_rsi(df) # 이렇게 하면 전체 시리즈가 아니므로 루프를 돌아야 함
    
    # 단순화를 위해 빈 컬럼 생성
    for col in ['rsi_14', 'macd_hist', 'macd_val', 'macd_sig', 'atr_14', 'ma5', 'ma20', 'ma60']:
        df[col] = 0.0
    df['regime'] = "NONE"
        
    print("지표 계산 중 (루프)...")
    for i in range(120, len(df)):
        window = df.iloc[i-120:i+1] # 현재 캔들 포함 과거 데이터
        indicators = {
            "rsi_14": calculate_rsi(window),
            "macd": calculate_macd(window),
            "atr_14": calculate_atr(window),
            "ma": calculate_ma(window)
        }
        df.loc[df.index[i], 'rsi_14'] = indicators['rsi_14']
        df.loc[df.index[i], 'macd_hist'] = indicators['macd']['histogram']
        df.loc[df.index[i], 'macd_val'] = indicators['macd']['macd']
        df.loc[df.index[i], 'macd_sig'] = indicators['macd']['signal']
        df.loc[df.index[i], 'atr_14'] = indicators['atr_14']
        
        ma = indicators['ma']
        df.loc[df.index[i], 'ma5'] = ma['ma5']
        df.loc[df.index[i], 'ma20'] = ma['ma20']
        df.loc[df.index[i], 'ma60'] = ma['ma60']
        
        if ma['ma5'] > ma['ma20'] > ma['ma60'] and indicators['macd']['histogram'] > 0:
            df.loc[df.index[i], 'regime'] = "AGGRESSIVE"
        elif ma['ma5'] < ma['ma20'] < ma['ma60'] and indicators['macd']['histogram'] < 0:
            df.loc[df.index[i], 'regime'] = "DEFENSIVE"
        else:
            df.loc[df.index[i], 'regime'] = "BALANCED"

    print("시뮬레이션 시작...")
    
    capital = START_CAPITAL
    position = 0.0
    entry_price = 0.0
    entry_atr = 0.0
    highest_price = 0.0
    
    trades = []
    
    cooldown_until = None
    kill_switch_until = None
    consecutive_losses = 0
    
    for i in range(120, len(df)-1):
        idx = df.index[i]
        row = df.loc[idx]
        
        if cooldown_until and idx < cooldown_until: continue
        if kill_switch_until and idx < kill_switch_until: continue
        
        # 청산 로직 (보유 중일 때)
        if position > 0:
            curr_high = row['high']
            curr_low = row['low']
            curr_close = row['close']
            
            # 장중 고가 갱신
            if curr_high > highest_price:
                highest_price = curr_high
                
            # Trailing Stop 가격 계산
            trailing_sl_price = entry_price - (ATR_STOP_LOSS * entry_atr) # 기본 손절
            
            if highest_price >= entry_price + (ATR_PROFIT_LOCK * entry_atr):
                trailing_sl_price = entry_price + (ATR_PROFIT_LOCK_RAISE * entry_atr)
            elif highest_price >= entry_price + (ATR_TRAILING_START * entry_atr):
                trailing_sl_price = highest_price - (ATR_TRAILING_DROP * entry_atr)
                
            # 장중 저가가 손절/트레일링 라인을 터치했는지 확인
            if curr_low <= trailing_sl_price:
                # 슬리피지 적용 체결가 (더 안 좋은 가격으로 체결 가정)
                exit_price = trailing_sl_price * (1 - SLIPPAGE) 
                
                # 가용 거래량이 부족해서 갭하락으로 체결될 수도 있으나 일단 터치 가격으로 계산
                revenue = position * exit_price
                revenue *= (1 - FEE) # 수수료 차감
                
                profit = revenue - (position * entry_price)
                capital += revenue
                
                is_win = profit > 0
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": idx,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "profit": profit,
                    "profit_pct": (exit_price / entry_price - 1) * 100
                })
                
                if not is_win:
                    consecutive_losses += 1
                    cooldown_until = idx + timedelta(hours=2)
                    if consecutive_losses >= 3:
                        kill_switch_until = idx + timedelta(hours=24)
                else:
                    consecutive_losses = 0
                    
                position = 0.0
                continue # 다음 캔들로
        
        # 진입 로직 (미보유 중일 때)
        if position == 0:
            # Rule Engine 조건 확인
            buy_signal = False
            
            rsi = row['rsi_14']
            macd_hist = row['macd_hist']
            macd_sig = row['macd_sig']
            macd_golden = row['macd_val'] > row['macd_sig']
            regime = row['regime']
            
            if rsi < 40 and macd_hist > 0:
                buy_signal = True
            elif regime == "AGGRESSIVE" and macd_golden and rsi < 65:
                buy_signal = True
                
            if buy_signal:
                # 다음 캔들 시가로 진입 가정
                next_open = df.iloc[i+1]['open']
                entry_price = next_open * (1 + SLIPPAGE)
                entry_atr = row['atr_14']
                
                # 리스크 1% 사이징
                risk_tolerance = capital * RISK_PER_TRADE
                stop_loss_pct = (ATR_STOP_LOSS * entry_atr) / entry_price
                
                if stop_loss_pct > 0:
                    target_krw = min(risk_tolerance / stop_loss_pct, capital)
                    target_krw *= (1 - FEE) # 매수 수수료 차감
                    
                    position = target_krw / entry_price
                    capital -= target_krw
                    
                    entry_time = df.index[i+1]
                    highest_price = entry_price

    # 리포트 출력
    print("\n=== 백테스트 결과 ===")
    total_trades = len(trades)
    if total_trades > 0:
        winning_trades = [t for t in trades if t['profit'] > 0]
        losing_trades = [t for t in trades if t['profit'] <= 0]
        
        win_rate = len(winning_trades) / total_trades * 100
        
        gross_profit = sum(t['profit'] for t in winning_trades)
        gross_loss = abs(sum(t['profit'] for t in losing_trades))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        avg_win = np.mean([t['profit_pct'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['profit_pct'] for t in losing_trades]) if losing_trades else 0
        
        print(f"총 거래 횟수: {total_trades}")
        print(f"승률: {win_rate:.2f}%")
        print(f"최종 자본: {capital + (position * df.iloc[-1]['close']):,.0f} KRW (초기: {START_CAPITAL:,.0f} KRW)")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"평균 익절: +{avg_win:.2f}% / 평균 손절: {avg_loss:.2f}%")
    else:
        print("조건을 만족하는 거래가 없었습니다.")

if __name__ == "__main__":
    run_backtest(days_back=40)
