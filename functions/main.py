from firebase_functions import https_fn, scheduler_fn
from firebase_admin import initialize_app, firestore
import json
import os
from datetime import datetime

# 로직 임포트
from .upbit_client import upbit_client
from .indicators import get_all_indicators
from .ai_engine import query_ai_decision
from .telegram_notifier import telegram_notifier
from .database import save_trade_log, save_ai_report

# 앱 초기화
initialize_app()
db = firestore.client()

def run_trading_logic():
    """트레이딩 분석 한 사이클 실행"""
    print(f"[{datetime.now()}] 클라우드 트레이딩 분석 시작...")
    
    try:
        # 1. 데이터 수집
        df = upbit_client.get_ohlcv(count=100)
        balances = upbit_client.get_balances()
        
        # 2. 지표 계산
        indicators = get_all_indicators(df)
        
        # 3. AI 의사결정 질의 (사용자 PC의 LM Studio 호출)
        decision_data = query_ai_decision(indicators, balances)
        decision = decision_data["decision"]
        reason = decision_data["reason"]
        percentage = decision_data["percentage"]
        
        # 🚨 잔고 부족 시 매수 방지 로직 (클라우드 환경 대응)
        krw = balances.get("krw", 0)
        if decision == "BUY" and krw < 5000:
            print(f"⚠️ 잔고 부족({krw:,.0f} 원)으로 인해 매수 결정을 HOLD로 전환합니다.")
            decision = "HOLD"
            reason = f"[잔고 부족으로 매수 취소] {reason}"
            percentage = 0.0
            
        # 4. 주문 실행 (MOCK_MODE에 따라 실제 또는 가상 실행)
        if decision in ["BUY", "SELL"]:
            order_res = upbit_client.execute_order(decision, percentage)
            if order_res["success"]:
                # 매매 로그 저장 (Firestore)
                save_trade_log(
                    decision=decision,
                    price=order_res["price"],
                    amount=order_res["amount"],
                    total_krw=order_res["total_krw"],
                    reason=reason
                )
                # 텔레그램 알림
                msg = f"⚡ *[자동 매매 체결]*\n• 결정: {decision}\n• 가격: {order_res['price']:,.0f} KRW\n• 총액: {order_res['total_krw']:,.0f} KRW\n• 이유: {reason}"
                telegram_notifier.send_message(msg)
        
        # 5. 분석 리포트 저장 (Firestore)
        save_ai_report(
            decision=decision,
            confidence=decision_data["confidence"],
            percentage=percentage,
            reason=reason,
            indicators=indicators
        )
        
        # 6. 자산 상태 업데이트 (대시보드용)
        db.collection('system').document('status').set({
            'last_update': datetime.now().isoformat(),
            'current_price': indicators.get('current_price'),
            'balances': balances
        })
        
        print(f"[{datetime.now()}] 분석 완료: {decision}")
        return True
    except Exception as e:
        print(f"에러 발생: {e}")
        return False

@scheduler_fn.on_schedule(schedule="every 60 minutes")
def scheduled_trading_analysis(event: scheduler_fn.ScheduledEvent) -> None:
    """Cloud Scheduler가 1시간마다 호출"""
    run_trading_logic()

@https_fn.on_request()
def trigger_manual_analysis(req: https_fn.Request) -> https_fn.Response:
    """수동 실행 API (CORS 허용 필요)"""
    # CORS 처리
    if req.method == "OPTIONS":
        return https_fn.Response(status=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    success = run_trading_logic()
    return https_fn.Response(
        json.dumps({"success": success}), 
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"}
    )
