import requests
import json
import re
from config import config
from exchange import PRICE_UNIT, CURRENCY_UNIT

def rule_engine_decision(indicators: dict) -> dict:
    """하드코딩된 기술적 지표 규칙 엔진 (진입 결정 담당)"""
    rsi = indicators.get("rsi_14", 50)
    macd = indicators.get("macd", {})
    bb = indicators.get("bollinger", {})
    ma = indicators.get("ma", {})
    
    current_price = indicators.get("current_price", 0)
    ma5, ma20, ma60 = ma.get("ma5", current_price), ma.get("ma20", current_price), ma.get("ma60", current_price)
    macd_hist, macd_val, macd_sig = macd.get("histogram", 0), macd.get("macd", 0), macd.get("signal", 0)
    macd_golden = macd_val > macd_sig
    
    ob_info = indicators.get("orderbook_imbalance", {})
    strong_buy_wall = ob_info.get("strong_buy_wall", False)
    
    vol_info = indicators.get("volume_trend", {})
    is_vol_spike = vol_info.get("is_volume_spike", False)
    
    if ma5 > ma20 > ma60 and macd_hist > 0:
        regime = "AGGRESSIVE"
    elif ma5 < ma20 < ma60 and macd_hist < 0:
        regime = "DEFENSIVE"
    else:
        regime = "BALANCED"

    # 규칙 1: 과매도 + 모멘텀 회복 (역추세 매수)
    if rsi < 40 and macd_hist > 0:
        return {"decision": "BUY", "reason": f"RSI {rsi:.1f} 반등 시그널 (단기 낙폭 과대)"}
        
    # 규칙 2: 강세장 추세 추종
    elif regime == "AGGRESSIVE" and macd_golden and rsi < 65:
        return {"decision": "BUY", "reason": "강세장 정배열 및 MACD 골든크로스 (추세 추종)"}
        
    # 허매수 덫 회피 (매도 기능 삭제, 신규 진입 차단만 함)
    elif strong_buy_wall and not is_vol_spike and rsi > 65:
        return {"decision": "HOLD", "reason": "허매수(Spoofing) 덫 징후 감지. 신규 진입 차단."}
        
    # 혼조세에서는 기본적으로 잦은 매매 금지 (Vhipsaw 방어)
    elif regime == "BALANCED" and not (rsi < 40 and macd_hist > macd_sig):
        return {"decision": "HOLD", "reason": "혼조세(BALANCED) 진입 차단 (휩쏘 방어)"}
        
    return {"decision": "HOLD", "reason": "명확한 진입 시그널 없음"}

def query_ai_veto(indicators: dict) -> dict:
    """LLM 거부권(Veto) 시스템: 규칙 엔진이 BUY를 외쳤을 때 뉴스/센티먼트 악재가 있는지 확인하여 차단함"""
    url = f"{config.LM_STUDIO_BASE_URL.rstrip('/')}/chat/completions"
    
    news_lines = "\n".join([f"- {news}" for news in indicators.get("recent_news", ["No recent news available"])])
    
    system_prompt = """You are a Veto (Rejection) Engine for a quantitative trading bot.
The algorithmic rule engine has ALREADY generated a 'BUY' signal based on technical charts.
Your ONLY job is to read the latest news headlines and VETO (reject) the trade IF there is a critical FUD (Fear, Uncertainty, Doubt) or major bad news (e.g., SEC lawsuits, hacks, massive sell-offs).
If the news is positive, neutral, or non-critical, you MUST NOT veto.

OUTPUT FORMAT (JSON ONLY):
{
  "veto": true | false,
  "reason": "Explain why you vetoed or allowed the trade based on the news (in Korean, max 2 sentences)"
}
"""

    user_prompt = f"""Recent News Headlines for XRP:
{news_lines}

Evaluate the news. Should we VETO the BUY signal? (true if bad news, false if okay)"""

    payload = {
        "model": config.LM_STUDIO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 500,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r'```json\s*|\s*```', '', content)
            
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match: content = json_match.group(1)
            
            parsed = json.loads(content)
            veto = bool(parsed.get("veto", False))
            reason = str(parsed.get("reason", "뉴스 분석 완료"))
            return {"veto": veto, "reason": reason}
    except Exception as e:
        print(f"LLM Veto 시스템 오류 (진행 허용): {e}")
        
    # 오류 시 기본적으로 Veto 하지 않음 (Rule 엔진을 우선시)
    return {"veto": False, "reason": "LLM Veto 시스템 응답 없음 (진입 허용)"}
