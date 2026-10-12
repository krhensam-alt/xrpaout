import requests
import json
import re
from config import config
from exchange import PRICE_UNIT, CURRENCY_UNIT

def rule_engine_decision(indicators: dict, is_holding: bool = False) -> dict:
    """돌파 추세추종 규칙 엔진 (마감된 봉 기준)

    - 진입: 종가가 직전 N봉 최고가를 돌파 + 종가가 추세 EMA 위
    - 청산: 종가가 추세 EMA 아래로 마감 (손절/트레일링은 trailing_stop_monitor 담당)
    """
    close = indicators.get("close", 0)
    ema = indicators.get("ema_trend", 0)
    breakout_high = indicators.get("breakout_high", float("inf"))

    if close <= 0 or ema <= 0:
        return {"decision": "HOLD", "reason": "지표 데이터 부족"}

    if is_holding:
        if close < ema:
            return {"decision": "SELL", "reason": f"추세 이탈: 종가 {close:,.2f} < EMA{config.TREND_EMA_PERIOD} {ema:,.2f}"}
        return {"decision": "HOLD", "reason": f"추세 유지 중 (종가 {close:,.2f} / EMA {ema:,.2f})"}

    if close > breakout_high and close > ema:
        return {"decision": "BUY", "reason": f"{config.BREAKOUT_PERIOD}봉 고가({breakout_high:,.2f}) 돌파 + EMA{config.TREND_EMA_PERIOD} 위 상승 추세"}
    if close <= ema:
        return {"decision": "HOLD", "reason": f"하락 추세 구간 (종가 {close:,.2f} < EMA {ema:,.2f}) 진입 금지"}
    return {"decision": "HOLD", "reason": f"돌파 대기 (기준 고가 {breakout_high:,.2f})"}

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
