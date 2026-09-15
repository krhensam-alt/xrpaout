import asyncio
import time
import traceback
from datetime import datetime, timedelta
from config import config
from exchange import exchange_client, CURRENCY_UNIT, PRICE_UNIT, MIN_ORDER_VALUE
from indicators import get_all_indicators
from ai_engine import rule_engine_decision, query_ai_veto
from database import save_ai_report, save_trade_log, get_ai_experiences, update_ai_report_outcome, get_db_connection
from telegram_notifier import send_telegram_message
import sqlite3
import os
import json

STATE_FILE = config.STATE_PATH

def load_trading_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                if "highest_price_since_buy" not in state: state["highest_price_since_buy"] = 0.0
                if "last_stop_loss_time" not in state: state["last_stop_loss_time"] = 0.0
                return state
        except Exception:
            pass
    return {"highest_price_since_buy": 0.0, "last_stop_loss_time": 0.0}

def save_trading_state(new_state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(new_state, f, indent=4)
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
        cutoff_time = (datetime.utcnow() - timedelta(minutes=55)).isoformat()
        cursor.execute("""
            SELECT id, decision, price_at_decision, timestamp 
            FROM ai_reports 
            WHERE outcome_status IS NULL 
            AND timestamp < ?
            ORDER BY id DESC LIMIT 20
        """, (cutoff_time,))
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

        # 🚨 글로벌 State 로드 (UnboundLocalError 방지)
        state = load_trading_state()

        # 최고가 상태 관리 (보유 중일 때만 업데이트)
        if xrp_amount * current_price > MIN_ORDER_VALUE and avg_buy_price > 0:
            highest_price = state.get("highest_price_since_buy", 0.0)
            
            # 초기화 혹은 갱신
            if highest_price <= 0.0 or highest_price < avg_buy_price:
                highest_price = max(avg_buy_price, current_price)
                
            if current_price > highest_price:
                highest_price = current_price
                state["highest_price_since_buy"] = highest_price
                save_trading_state(state)
                print(f"📈 최고가 갱신: {highest_price:,.4f} {PRICE_UNIT}")

            # 참고: 실시간 손절 및 트레일링 익절은 trailing_stop_monitor가 전담합니다.
            # 여기서는 중복 청산을 방지하기 위해 정규 사이클의 청산 로직을 완전히 제거했습니다.

        # 3.2. 거래소 안전 예약 주문(안전장치) 실시간 점검 및 복구 로직
        if xrp_amount * current_price > MIN_ORDER_VALUE and avg_buy_price > 0:
            print("🛡️ 거래소 안전 예약 주문(안전장치) 상태 점검 중...")
            try:
                safety_active = exchange_client.check_safety_orders(xrp_amount, avg_buy_price)
                if not safety_active:
                    print("⚠️ 거래소 안전 예약 주문이 유실된 것을 감지했습니다. 재등록을 시도합니다.")
                    # send_telegram_message("⚠️ *[안전장치 유실 감지]*\n거래소에 직접 등록된 안전 예약 주문(지정가/OCO)이 유실된 것을 감지했습니다. 재등록을 진행합니다.")
                    
                    # 꼬임 방지를 위해 기존 미체결 주문 취소 후 재등록
                    exchange_client.cancel_all_orders()
                    safety_res = exchange_client.place_safety_orders(xrp_amount, avg_buy_price)
                    if safety_res.get("success"):
                        print("🛡️ 거래소 안전 예약 주문 재등록 완료")
                        # send_telegram_message("🛡️ *[안전장치 재가동 완료]*\n거래소 서버에 안전 예약 주문을 성공적으로 재등록했습니다.")
                    else:
                        err_reason = safety_res.get("reason", "알 수 없는 오류")
                        print(f"❌ 안전장치 재등록 실패: {err_reason}")
                        # send_telegram_message(f"❌ *[안전장치 재등록 실패]*\n사유: `{err_reason}`")
                else:
                    print("🛡️ 거래소 안전 예약 주문(안전장치)이 정상 작동 중입니다.")
            except Exception as safety_err:
                print(f"⚠️ 안전장치 검증 중 오류 발생: {safety_err}")

        # 3.5. 과거 판단 복기 (사후 평가용, 새 로직에서는 경험 데이터를 LLM에 전달하지 않음)
        await evaluate_past_reports(current_price)

        # 3.6. 고래 매수세/호가창 및 실시간 뉴스 수집
        print("고래 움직임 및 최신 뉴스 데이터 수집 중...")
        ob_imbalance = exchange_client.get_orderbook_imbalance()
        indicators["orderbook_imbalance"] = ob_imbalance
        
        from news_client import news_client
        latest_news = news_client.get_latest_xrp_news()
        indicators["recent_news"] = latest_news

        # 4. 규칙 엔진 의사결정 및 LLM Veto
        print("규칙 엔진 의사결정 진행 중...")
        
        rule_res = rule_engine_decision(indicators)
        decision = rule_res.get("decision", "HOLD")
        reason = rule_res.get("reason", "")
        
        # Rule Engine이 BUY를 외치면 LLM에게 뉴스 악재(Veto) 확인
        if decision == "BUY":
            print("LLM Veto 시스템에 악재 뉴스 확인 중...")
            veto_res = query_ai_veto(indicators)
            if veto_res.get("veto", False):
                print(f"🛑 LLM Veto 발동! 매수 기각: {veto_res.get('reason', '')}")
                decision = "HOLD"
                reason = f"규칙 엔진 매수(BUY) -> LLM 거부권 행사(Veto): {veto_res.get('reason', '')}"
            else:
                print("✅ LLM Veto 통과. 뉴스 악재 없음.")
                reason = f"{reason} (LLM 검증 완료: {veto_res.get('reason', '')})"
        
        # 4.5. 포지션 사이징 (리스크 기반 1% 룰 적용)
        confidence = 1.0 # 룰 엔진은 100% 확신으로 간주
        percentage = 0.0
        if decision == "BUY":
            main_cash = balances.get("krw" if config.SELECTED_EXCHANGE == "UPBIT" else "usdt", 0)
            risk_tolerance = main_cash * 0.01 # 총 가용 현금의 1%를 최대 손실로 고정
            
            # 튜닝된 손절 비율 사용 (기본 1.5)
            optim_sl = state.get("optim_stop_loss", 1.5)
            atr_val = indicators.get("atr_14", current_price * 0.02)
            stop_loss_pct = (optim_sl * atr_val) / current_price
            
            if stop_loss_pct > 0:
                target_krw = risk_tolerance / stop_loss_pct
            else:
                target_krw = 0.0
                
            # 가용 현금 내에서만 매수 (최대 100%)
            target_krw = min(target_krw, main_cash)
            percentage = (target_krw / main_cash * 100.0) if main_cash > 0 else 0.0
            print(f"포지션 사이징: 투입금 {target_krw:,.0f} 원 (현금 비중 {percentage:.1f}%) / 손절폭 {stop_loss_pct*100:.2f}%")
            
        elif decision == "SELL":
            percentage = 100.0
        
        # 🚨 리스크 관리: 킬스위치 및 쿨타임 로직
        last_sl_time = state.get("last_stop_loss_time", 0.0)
        kill_switch_until = state.get("kill_switch_until", 0.0)
        current_time = time.time()
        
        if decision == "BUY":
            if current_time < kill_switch_until:
                print("🚨 킬스위치 작동 중: 연속 손절로 인해 매수가 차단되었습니다.")
                decision = "HOLD"
                reason = f"[킬스위치 발동] 연속 3회 손절로 인한 24시간 매수 금지 상태입니다. {reason}"
                percentage = 0.0
            elif current_time - last_sl_time < 2 * 3600:
                print("⚠️ 손절매 이후 쿨타임(2시간)이 지나지 않아 매수를 보류합니다.")
                decision = "HOLD"
                reason = f"[쿨타임 적용] 최근 손절매 이후 안정화 대기 중. {reason}"
                percentage = 0.0

        # 🚨 잔고 부족 시 매수 방지 로직 추가
        main_cash = balances.get("krw" if config.SELECTED_EXCHANGE == "UPBIT" else "usdt", 0)
        
        # 🚨 일일 손실 한도 (-4%) 방어망
        today_str = datetime.now().strftime("%Y-%m-%d")
        total_asset = main_cash + (balances.get("xrp", 0) * current_price)
        daily_start_cap = state.get(f"daily_start_{today_str}", total_asset)
        
        if f"daily_start_{today_str}" not in state:
            state[f"daily_start_{today_str}"] = total_asset
            save_trading_state(state)
            daily_start_cap = total_asset
            
        daily_pnl_pct = ((total_asset - daily_start_cap) / daily_start_cap * 100) if daily_start_cap > 0 else 0.0
        
        if decision == "BUY" and daily_pnl_pct <= -4.0:
            print(f"🛑 [일일 손실 한도 도달] 당일 손실이 {daily_pnl_pct:.2f}%로 -4%를 초과하여 매수를 전면 차단합니다.")
            decision = "HOLD"
            reason = f"[일일 손실 차단] 당일 누적 손실 {daily_pnl_pct:.2f}%로 -4% 한도 초과"
            percentage = 0.0
            
            # 일일 손실 한도 도달 시에도 튜닝 트리거
            last_tuning = state.get("last_tuning_time", 0)
            # 하루에 한 번만 실행되도록 제한 (너무 잦은 실행 방지)
            if time.time() - last_tuning > 12 * 3600:
                print("🛑 일일 손실 방어망 작동. Auto-Tuning을 시작합니다.")
                from auto_optimizer import run_auto_optimization
                asyncio.create_task(run_auto_optimization())
        elif decision == "BUY" and main_cash < MIN_ORDER_VALUE:
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
        
        # 텔레그램 정기 보고 (핵심 팩트만 간결하게)
        state = load_trading_state()
        initial_krw = state.get("investment_base", float(config.MAX_INVESTMENT_KRW))
        total_val = balances.get("total_val", 0)
        krw_bal = balances.get("krw", 0)
        xrp_bal = balances.get("xrp", 0)
        avg_buy = balances.get("avg_buy_price", 0)
        
        pnl_krw = total_val - initial_krw
        pnl_sign = "+" if pnl_krw > 0 else ""
        pnl_percent = (pnl_krw / initial_krw * 100) if initial_krw > 0 else 0
        
        tg_report = (
            f"📊 *[XRP 정기 보고]*\n"
            f"• 원금: `{initial_krw:,.0f}` KRW\n"
            f"• 자산: `{total_val:,.0f}` KRW (KRW:`{krw_bal:,.0f}`)\n"
            f"• 손익: *{pnl_sign}{pnl_krw:,.0f} KRW* ({pnl_sign}{pnl_percent:.2f}%)\n"
            f"• XRP: `{xrp_bal:,.2f}` 개 (평단: `{avg_buy:,.2f}`)\n"
            f"• AI 판단: *{decision}*"
        )
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
                
                # 최고가 및 진입 정보 상태 관리 파일 업데이트
                if decision == "BUY":
                    # 신규 진입 시 손절 기준이 되는 atr과 평단가 저장
                    s = load_trading_state()
                    s["highest_price_since_buy"] = price
                    s["entry_price"] = price
                    s["entry_atr"] = indicators.get("atr_14", price * 0.02)
                    save_trading_state(s)
                elif decision == "SELL":
                    s = load_trading_state()
                    s["highest_price_since_buy"] = 0.0
                    s.pop("entry_price", None)
                    s.pop("entry_atr", None)
                    save_trading_state(s)
                
                # 🛡️ 서버 다운 대비 예약 주문(Safety Net) 즉시 실행
                safety_res = exchange_client.place_safety_orders(amount, price)
                if safety_res.get("success"):
                    print(f"🛡️ 거래소 기반 안전 예약 주문 완료 (서버 중단 대비)")
                    # send_telegram_message(f"🛡️ *[안전장치 가동]*\n거래소 서버에 직접 예약 주문을 등록했습니다. 이제 서버가 중단되어도 목표가 도달 시 자동으로 매도됩니다.")
                
                # 주문 체결 텔레그램 알림 (사용자 요청으로 생략)
                # tg_trade = f"⚡ *[AI 자동 매매 체결 성공]*\n• 포지션: *{decision}*\n• 체결가: `{price:,.4f}` {PRICE_UNIT}\n• 수량: `{amount:,.4f}` XRP\n• 총액: `{total_krw:,.0f}` {CURRENCY_UNIT}\n• 근거 요약:\n_{reason}_"
                # send_telegram_message(tg_trade)
                
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

async def trailing_stop_monitor():
    """1분마다 가격을 확인하여 트레일링 스탑 적용"""
    while True:
        await asyncio.sleep(60)
        try:
            state = load_trading_state()
            balances = exchange_client.get_balances()
            xrp_bal = balances.get("xrp", 0)
            
            if xrp_bal > 0:
                current_price = exchange_client.get_current_price()
                avg_buy_price = balances.get("avg_buy_price", 0)
                highest_price = state.get("highest_price_since_buy", 0)
                
                entry_price = state.get("entry_price", avg_buy_price)
                
                # ATR 정보가 없으면 기본값(2%) 사용
                entry_atr = state.get("entry_atr", current_price * 0.02)
                
                if current_price > highest_price:
                    highest_price = current_price
                    state["highest_price_since_buy"] = highest_price
                    save_trading_state(state)
                    
                # 자가 튜닝된 파라미터 로드
                ATR_TRAILING_START = state.get("optim_trailing_start", 1.5)
                ATR_TRAILING_DROP = state.get("optim_trailing_drop", 0.75)
                ATR_STOP_LOSS = state.get("optim_stop_loss", 1.5)
                
                # 손절 라인 및 트레일링 익절 라인 계산
                trailing_sl_price = entry_price - (ATR_STOP_LOSS * entry_atr) # 기본 손절 라인
                
                # 1. 수익 잠금 (+3 ATR 도달 시 진입가 + 1 ATR로 상향)
                ATR_PROFIT_LOCK = 3.0
                ATR_PROFIT_LOCK_RAISE = 1.0
                if highest_price >= entry_price + (ATR_PROFIT_LOCK * entry_atr):
                    trailing_sl_price = entry_price + (ATR_PROFIT_LOCK_RAISE * entry_atr)
                # 2. 트레일링 스탑 (+1.5 ATR 도달 시)
                elif highest_price >= entry_price + (ATR_TRAILING_START * entry_atr):
                    trailing_sl_price = highest_price - (ATR_TRAILING_DROP * entry_atr)
                    
                # 현재가가 기준선 아래로 떨어졌는지 확인
                if current_price <= trailing_sl_price:
                    is_stop_loss = current_price < entry_price
                    action_name = "손절매" if is_stop_loss else "트레일링 익절"
                    print(f"🎯 {action_name} 발동! 기준가({trailing_sl_price:,.2f}) 이탈. 전량 매도 진행.")
                    
                    # 전량 매도 실행
                    order_res = exchange_client.execute_order("SELL", 100.0)
                    if order_res.get("success"):
                        price = order_res.get("price", current_price)
                        amount = order_res.get("amount", xrp_bal)
                        total_krw = order_res.get("total_krw", price * amount)
                        reason = f"{action_name} 발동 (고점 {highest_price:,.2f}, 하락 이탈)"
                        save_trade_log("SELL", price, amount, total_krw, reason)
                        
                        new_state = state.copy()
                        new_state["highest_price_since_buy"] = 0.0
                        new_state.pop("entry_price", None)
                        new_state.pop("entry_atr", None)
                        
                        if is_stop_loss:
                            consecutive = new_state.get("consecutive_losses", 0) + 1
                            new_state["consecutive_losses"] = consecutive
                            new_state["last_stop_loss_time"] = time.time()
                            
                            # 🚨 킬스위치 도달 시 Auto-Tuning 발동
                            if consecutive >= 3:
                                new_state["kill_switch_until"] = time.time() + (24 * 3600)
                                print("🚨 킬스위치 발동. Auto-Tuning을 시작합니다.")
                                from auto_optimizer import run_auto_optimization
                                asyncio.create_task(run_auto_optimization())
                        else:
                            new_state["consecutive_losses"] = 0
                            
                        save_trading_state(new_state)
                        
                        # 웹소켓 브로드캐스트
                        await notify_subscribers("new_trade", {
                            "decision": "SELL",
                            "price": price,
                            "amount": amount,
                            "total_krw": total_krw,
                            "reason": reason,
                            "timestamp": datetime.now().isoformat()
                        })
                        print(f"주문 체결 성공: SELL | 수량: {amount:.4f} | 총액: {total_krw:.0f}{CURRENCY_UNIT}")
        except Exception as e:
            print(f"Trailing Stop 오류: {e}")

async def start_scheduler():
    """백그라운드 주기적 실행 루프 (정각/배수 시간 정렬)"""
    interval_minutes = config.TRADING_INTERVAL_MINUTES
    
    # 서버 기동 직후 즉시 1회 실행하여 DB 및 화면 초기 데이터 확보
    await execute_trading_cycle()
    
    # 트레일링 스탑 모니터 시작 (백그라운드 루프)
    asyncio.create_task(trailing_stop_monitor())
    
    while True:
        # 현재 시간 기준으로 다음 정렬된 시간까지 대기
        now = datetime.now()
        # 다음 실행 시간 계산 (예: 60분 간격이면 다음 00분, 15분 간격이면 다음 15, 30, 45, 00분)
        minutes_to_wait = interval_minutes - (now.minute % interval_minutes)
        seconds_to_wait = (minutes_to_wait * 60) - now.second
        
        if seconds_to_wait <= 0:
            seconds_to_wait = interval_minutes * 60
            
        print(f"⏱️ 다음 분석 사이클까지 {seconds_to_wait}초 대기합니다. (약 {minutes_to_wait}분 후)")
        await asyncio.sleep(seconds_to_wait)
        await execute_trading_cycle()
