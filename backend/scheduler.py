import asyncio
import time
import traceback
from datetime import datetime
from config import config
from exchange import exchange_client, CURRENCY_UNIT, PRICE_UNIT, MIN_ORDER_VALUE
from indicators import get_all_indicators
from ai_engine import query_ai_decision
from database import save_ai_report, save_trade_log, get_ai_experiences, update_ai_report_outcome, get_db_connection
from telegram_notifier import send_telegram_message
import sqlite3
import os
import json

STATE_FILE = os.path.join(os.path.dirname(__file__), "trading_state.json")

def load_trading_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"highest_price_since_buy": 0.0}

def save_trading_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"상태 파일 저장 오류: {e}")

# 브로드캐스팅용 콜백 함수 목록 관리
broadcast_callbacks = []

def register_callback(cb):
    broadcast_callbacks.append(cb)

async def notify_subscribers(event_type: str, data: dict):
    for cb in broadcast_callbacks:
        try:
            if asyncio.iscoroutinefunction(cb):
                await cb(event_type, data)
            else:
                cb(event_type, data)
        except Exception as e:
            print(f"브로드캐스트 알림 오류: {e}")

async def evaluate_past_reports(current_price: float):
    """과거의 AI 판단이 적절했는지 현재가와 비교하여 성적표 작성 (Self-Evaluation)"""
    print("과거 AI 판단 결과 복기 중...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 아직 평가되지 않았고, 55분 이상 경과한 리포트 조회 (이전 시간 분석 결과를 다음 시간 분석 시점에 바로 경험으로 활용)
        cursor.execute("""
            SELECT id, decision, price_at_decision, timestamp 
            FROM ai_reports 
            WHERE outcome_status IS NULL 
            AND timestamp < datetime('now', '-55 minutes')
            ORDER BY id DESC LIMIT 20
        """)
        pending_reports = cursor.fetchall()
        conn.close()

        for report in pending_reports:
            r_id, decision, start_price, r_ts = report
            if not start_price or start_price == 0: continue
            
            pnl_rate = ((current_price - start_price) / start_price) * 100.0
            status = "NEUTRAL"
            
            if decision == "BUY":
                status = "SUCCESS" if pnl_rate > 0.5 else "FAILURE" if pnl_rate < -0.5 else "NEUTRAL"
            elif decision == "SELL":
                status = "SUCCESS" if pnl_rate < -0.5 else "FAILURE" if pnl_rate > 0.5 else "NEUTRAL"
            elif decision == "HOLD":
                # HOLD는 변동성이 적을 때 성공으로 간주하거나, 큰 기회를 놓치지 않았을 때 성공
                status = "SUCCESS" if abs(pnl_rate) < 1.0 else "NEUTRAL"
            
            update_ai_report_outcome(r_id, current_price, status, pnl_rate)
            print(f"리포트 #{r_id} 복기 완료: 결정={decision}, 수익률={pnl_rate:.2f}%, 결과={status}")
            
    except Exception as e:
        print(f"사후 평가 루프 오류: {e}")

async def execute_trading_cycle(is_forced: bool = False):
    """1회 트레이딩 파이프라인 사이클 실행"""
    print(f"\n[{datetime.now().isoformat()}] 트레이딩 분석 사이클을 시작합니다...")
    try:
        # 1. 데이터 수집
        print("데이터 수집 중...")
        df = exchange_client.get_ohlcv()
        if df is None or df.empty:
            print("캔들 데이터 수집 실패로 이번 사이클을 건너뜁니다.")
            return

        # 2. 지표 계산
        print("지표 계산 중...")
        indicators = get_all_indicators(df)
        
        # 3. 잔고 및 평단가 조회
        print("잔고 조회 중...")
        balances = exchange_client.get_balances()
        avg_buy_price = balances.get("avg_buy_price", 0.0)
        current_price = indicators.get("current_price", 0.0)
        xrp_amount = balances.get("xrp", 0.0)

        # 🚨 최우선 기계적 리스크 관리 필터 (추적 손절매 및 익절매 잠금)
        if xrp_amount * current_price > MIN_ORDER_VALUE and avg_buy_price > 0:
            state = load_trading_state()
            highest_price = state.get("highest_price_since_buy", 0.0)
            
            # 초기화 혹은 갱신
            if highest_price <= 0.0 or highest_price < avg_buy_price:
                highest_price = max(avg_buy_price, current_price)
                
            if current_price > highest_price:
                highest_price = current_price
                save_trading_state({"highest_price_since_buy": highest_price})
                print(f"📈 최고가 갱신: {highest_price:,.4f} {PRICE_UNIT}")

            highest_profit_rate = ((highest_price - avg_buy_price) / avg_buy_price) * 100.0
            current_profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100.0

            # 추적 손절라인 계산
            # 1. 최고수익률이 +5.0% 이상 도달한 적이 있으면 최고가 대비 -2.5% 추적 익절/손절 적용 (추세 극대화)
            if highest_profit_rate >= 5.0:
                trailing_sl_price = highest_price * 0.975
                trigger_reason = f"최고 수익률 {highest_profit_rate:.2f}% 도달 후 최고가({highest_price:,.4f}) 대비 -2.5% 추적 매도"
                is_triggered = current_price <= trailing_sl_price
                sl_type = "추적 익절매" if trailing_sl_price > avg_buy_price else "추적 손절매"
            # 2. 최고수익률이 +3.0% ~ +5.0% 도달한 적이 있으면 +1.0% 수익 안전 확보 (수익 잠금)
            elif highest_profit_rate >= 3.0:
                trailing_sl_price = avg_buy_price * 1.01
                trigger_reason = f"최고 수익률 {highest_profit_rate:.2f}% 도달 후 +1.0% 수익 안전 확보 매도"
                is_triggered = current_price <= trailing_sl_price
                sl_type = "수익 확보 매도"
            # 3. 기본 손절 라인 (-3.5% 고정)
            else:
                trailing_sl_price = avg_buy_price * 0.965
                trigger_reason = f"평단가 대비 -3.5% 하락으로 인한 계좌 보호 손절매"
                is_triggered = current_profit_rate <= -3.5
                sl_type = "기본 손절매"

            if is_triggered:
                print(f"🚨 [{sl_type} 발동] 현재가({current_price})가 손절라인({trailing_sl_price:,.4f}) 도달. 사유: {trigger_reason}")
                order_res = exchange_client.execute_order("SELL", 100.0)
                if order_res.get("success"):
                    exec_reason = f"[{sl_type} 집행] {trigger_reason}"
                    save_trade_log("SELL", current_price, xrp_amount, xrp_amount * current_price, exec_reason)
                    
                    # 텔레그램 실시간 알림 발송
                    tg_msg = f"🚨 *[{sl_type} 집행]*\n• 종목: XRP\n• 현재가: `{current_price:,.4f}` {PRICE_UNIT}\n• 매수평단: `{avg_buy_price:,.4f}` {PRICE_UNIT}\n• 최고수익률: *+{highest_profit_rate:.2f}%*\n• 현재수익률: *{current_profit_rate:+.2f}%*\n• 사유: {trigger_reason}"
                    send_telegram_message(tg_msg)
                    
                    await notify_subscribers("new_trade", {
                        "decision": "SELL", "price": current_price, "amount": xrp_amount,
                        "total_krw": xrp_amount * current_price, "reason": exec_reason,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 상태 초기화
                    save_trading_state({"highest_price_since_buy": 0.0})
                    
                await notify_subscribers("balance_update", exchange_client.get_balances())
                return

        # 3.2. 거래소 안전 예약 주문(안전장치) 실시간 점검 및 복구 로직
        if xrp_amount * current_price > MIN_ORDER_VALUE and avg_buy_price > 0:
            print("🛡️ 거래소 안전 예약 주문(안전장치) 상태 점검 중...")
            try:
                safety_active = exchange_client.check_safety_orders(xrp_amount, avg_buy_price)
                if not safety_active:
                    print("⚠️ 거래소 안전 예약 주문이 유실된 것을 감지했습니다. 재등록을 시도합니다.")
                    send_telegram_message("⚠️ *[안전장치 유실 감지]*\n거래소에 직접 등록된 안전 예약 주문(지정가/OCO)이 유실된 것을 감지했습니다. 재등록을 진행합니다.")
                    
                    # 꼬임 방지를 위해 기존 미체결 주문 취소 후 재등록
                    exchange_client.cancel_all_orders()
                    safety_res = exchange_client.place_safety_orders(xrp_amount, avg_buy_price)
                    if safety_res.get("success"):
                        print("🛡️ 거래소 안전 예약 주문 재등록 완료")
                        send_telegram_message("🛡️ *[안전장치 재가동 완료]*\n거래소 서버에 안전 예약 주문을 성공적으로 재등록했습니다.")
                    else:
                        err_reason = safety_res.get("reason", "알 수 없는 오류")
                        print(f"❌ 안전장치 재등록 실패: {err_reason}")
                        send_telegram_message(f"❌ *[안전장치 재등록 실패]*\n사유: `{err_reason}`")
                else:
                    print("🛡️ 거래소 안전 예약 주문(안전장치)이 정상 작동 중입니다.")
            except Exception as safety_err:
                print(f"⚠️ 안전장치 검증 중 오류 발생: {safety_err}")

        # 3.5. 과거 판단 복기 및 경험 데이터 로드
        await evaluate_past_reports(current_price)
        experiences = get_ai_experiences(limit=5)

        # 4. AI 의사결정 질의 (경험 데이터 주입)
        print("AI 의사결정 질의 중 (경험 기반 학습 적용)...")
        ai_res = query_ai_decision(indicators, balances, experiences)
        decision = ai_res.get("decision", "HOLD")
        confidence = ai_res.get("confidence", 0.5)
        percentage = ai_res.get("percentage", 0.0)
        reason = ai_res.get("reason", "")
        
        # 🚨 잔고 부족 시 매수 방지 로직 추가
        main_cash = balances.get("krw" if config.SELECTED_EXCHANGE == "UPBIT" else "usdt", 0)
        if decision == "BUY" and main_cash < MIN_ORDER_VALUE:
            print(f"⚠️ 잔고 부족({main_cash:,.0f} {PRICE_UNIT})으로 인해 매수 결정을 HOLD로 전환합니다.")
            decision = "HOLD"
            reason = f"[잔고 부족으로 매수 취소] {reason}"
            percentage = 0.0

        # 거시 지표 기반 필터링 보완: 비트코인 단기 급락 추세 시 매수 차단 및 보류
        btc_change_rate = exchange_client.get_btc_change_rate()
        if decision == "BUY" and btc_change_rate <= -1.5:
            print(f"⚠️ [매수 차단] 비트코인 단기 급락 감지 (변동률: {btc_change_rate:.2f}%). 매수 결정을 보류하고 HOLD로 전환합니다.")
            decision = "HOLD"
            reason = f"[비트코인 급락으로 매수 차단] 비트코인 1시간 변동률 {btc_change_rate:.2f}%로 급락 경고 감지."
            percentage = 0.0
        elif decision == "BUY" and btc_change_rate > -1.5:
            reason += f" (참조: 비트코인 변동률 {btc_change_rate:+.2f}%로 안정적인 마켓 상황 확인)"
            
        # AI 리포트 DB 저장 (현재가 포함)
        save_ai_report(decision, confidence, percentage, reason, indicators, current_price)
        
        # 텔레그램 정기 분석 리포트 발송 (매 주기마다 포지션 및 확신도 무관하게 항상 발송)
        tg_report = f"🧠 *[XRP 퀀트 AI 판단 리포트]*\n• 전략 결정: *{decision}* (`{confidence*100:.0f}%` 확신)\n• 비중: `{percentage}%`\n• 현재가: `{current_price:,.4f}` {PRICE_UNIT}\n• 보조 지표: RSI `{indicators.get('rsi_14',50):.1f}`\n• 상세 사유:\n_{reason}_"
        send_telegram_message(tg_report)
            
        await notify_subscribers("new_report", {
            "decision": decision,
            "confidence": confidence,
            "percentage": percentage,
            "reason": reason,
            "indicators": indicators,
            "timestamp": datetime.now().isoformat()
        })
        
        # 5. 주문 실행 (BUY / SELL인 경우)
        if decision in ("BUY", "SELL") and percentage > 0:
            order_res = exchange_client.execute_order(decision, percentage)
            if order_res.get("success"):
                price = order_res.get("price", indicators.get("current_price", 0))
                amount = order_res.get("amount", 0)
                total_krw = order_res.get("total_krw", 0)
                exec_reason = f"[{decision}] AI 판단에 따른 자동 실행: {reason}"
                
                save_trade_log(decision, price, amount, total_krw, exec_reason)
                
                # 최고가 상태 관리 파일 업데이트
                if decision == "BUY":
                    save_trading_state({"highest_price_since_buy": price})
                elif decision == "SELL":
                    save_trading_state({"highest_price_since_buy": 0.0})
                
                # 🛡️ 서버 다운 대비 예약 주문(Safety Net) 즉시 실행
                safety_res = exchange_client.place_safety_orders(amount, price)
                if safety_res.get("success"):
                    print(f"🛡️ 거래소 기반 안전 예약 주문 완료 (서버 중단 대비)")
                    send_telegram_message(f"🛡️ *[안전장치 가동]*\n거래소 서버에 직접 예약 주문을 등록했습니다. 이제 서버가 중단되어도 목표가 도달 시 자동으로 매도됩니다.")
                
                # 주문 체결 텔레그램 알림
                tg_trade = f"⚡ *[AI 자동 매매 체결 성공]*\n• 포지션: *{decision}*\n• 체결가: `{price:,.4f}` {PRICE_UNIT}\n• 수량: `{amount:,.4f}` XRP\n• 총액: `{total_krw:,.0f}` {CURRENCY_UNIT}\n• 근거 요약:\n_{reason}_"
                send_telegram_message(tg_trade)
                
                await notify_subscribers("new_trade", {
                    "decision": decision,
                    "price": price,
                    "amount": amount,
                    "total_krw": total_krw,
                    "reason": exec_reason,
                    "timestamp": datetime.now().isoformat()
                })
                print(f"주문 체결 성공: {decision} | 수량: {amount:.4f} | 총액: {total_krw:.0f}{CURRENCY_UNIT}")
            else:
                fail_reason = order_res.get("reason", "알 수 없는 사유")
                print(f"주문 실행 실패: {fail_reason}")
        else:
            print(f"이번 사이클 의사결정: {decision} ({reason})")
            
        # 자산 상태 업데이트 브로드캐스트
        new_balances = exchange_client.get_balances()
        await notify_subscribers("balance_update", new_balances)
        
    except Exception as e:
        error_msg = f"❌ *트레이딩 사이클 치명적 오류 발생*\n사유: `{str(e)}`"
        print(f"트레이딩 사이클 실행 중 치명적 오류 발생: {e}")
        traceback.print_exc()
        send_telegram_message(error_msg)

async def start_scheduler():
    """백그라운드 주기적 실행 루프 (정각/배수 시간 정렬)"""
    interval_minutes = config.TRADING_INTERVAL_MINUTES
    
    # 서버 기동 직후 즉시 1회 실행하여 DB 및 화면 초기 데이터 확보
    await execute_trading_cycle()
    
    while True:
        # 현재 시간 기준으로 다음 정렬된 시간까지 대기
        now = datetime.now()
        # 다음 실행 시간 계산 (예: 60분 간격이면 다음 00분, 10분 간격이면 다음 10, 20, ... 분)
        minutes_to_wait = interval_minutes - (now.minute % interval_minutes)
        seconds_to_wait = (minutes_to_wait * 60) - now.second
        
        if seconds_to_wait <= 0:
            seconds_to_wait = interval_minutes * 60
            
        print(f"⏱️ 다음 분석 사이클까지 {seconds_to_wait}초 대기합니다. (약 {minutes_to_wait}분 후)")
        await asyncio.sleep(seconds_to_wait)
        await execute_trading_cycle()
