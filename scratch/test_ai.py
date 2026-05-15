import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.append(os.getcwd())

from backend.ai_engine import query_ai_decision

# 가상 데이터
indicators = {
    "current_price": 750.0,
    "rsi_14": 40.0,
    "macd": {"histogram": 0.001, "macd": 0.5, "signal": 0.4},
    "bollinger": {"upper": 800, "lower": 700, "mid": 750},
    "ma": {"ma5": 760, "ma20": 740, "ma60": 720}
}
balances = {
    "krw": 100000,
    "xrp": 0,
    "avg_buy_price": 0,
    "total_val": 100000
}

print("AI 질의 테스트를 시작합니다...")
try:
    result = query_ai_decision(indicators, balances)
    print("AI 응답 성공!")
    print(f"결정: {result['decision']}")
    print(f"이유: {result['reason']}")
    print(f"확신도: {result['confidence']}")
    print(f"비중: {result['percentage']}")
except Exception as e:
    print(f"AI 질의 중 오류 발생: {e}")
