import requests
import json
import re
from .config import config
from .exchange import PRICE_UNIT, CURRENCY_UNIT

def query_ai_decision(indicators: dict, balances: dict, experiences: dict = None) -> dict:
    """LM Studio REST API를 통해 의사결정 질의 및 과거 경험 기반 학습(RAG) 적용"""
    url = f"{config.LM_STUDIO_BASE_URL.rstrip('/')}/chat/completions"

    current_price = indicators.get("current_price", 0)
    rsi = indicators.get("rsi_14", 50)
    macd = indicators.get("macd", {})
    bb = indicators.get("bollinger", {})
    ma = indicators.get("ma", {})
    
    # 잔고 정보 (거래소에 따라 usdt 또는 krw가 주 통화가 됨)
    main_cash = balances.get("usdt" if config.SELECTED_EXCHANGE == "BINANCE" else "krw", 0)
    xrp = balances.get("xrp", 0)
    avg_buy = balances.get("avg_buy_price", 0)
    total_val = balances.get("total_val", 0)
    profit_rate = ((current_price - avg_buy) / avg_buy * 100) if avg_buy > 0 else 0.0

    # 볼린저 밴드 위치 계산
    bb_upper = bb.get("upper", current_price)
    bb_lower = bb.get("lower", current_price)
    bb_mid = bb.get("mid", current_price)
    bb_range = bb_upper - bb_lower
    bb_position_pct = ((current_price - bb_lower) / bb_range * 100) if bb_range > 0 else 50.0

    # ── 시장 국면 분석 (Market Regime Detection) ──────────────────────────
    ma5 = ma.get("ma5", current_price)
    ma20 = ma.get("ma20", current_price)
    ma60 = ma.get("ma60", current_price)
    macd_hist = macd.get("histogram", 0)

    # 국면 판단 로직
    if ma5 > ma20 > ma60 and macd_hist > 0:
        regime = "AGGRESSIVE (강세장 - 수익 극대화)"
        persona = "공격적 성향의 트렌드 헌터"
        rules = """- 상승 추세가 강력하므로 눌림목에서 적극적으로 진입하세요.
- RSI 50 이하 또는 볼린저 중단 근처에서도 분할 매수를 고려합니다.
- 익절은 RSI 75 이상이나 추세가 꺾일 때까지 최대한 길게 가져갑니다."""
        base_pct = 50
    elif ma5 < ma20 < ma60 and macd_hist < 0:
        regime = "DEFENSIVE (약세장 - 자산 방어)"
        persona = "보수적 성향의 자산 관리자"
        rules = """- 하락 압력이 크므로 극도의 저점 부근에서 신중하게 진입하세요.
- RSI 35 이하 + 확실한 반등 근거(밑꼬리, 거래량)가 있을 때만 진입합니다.
- 작은 반등에도 빠르게 수익을 실현(RSI 55~60 부근)하여 현금 비중을 확보하세요."""
        base_pct = 20
    else:
        regime = "BALANCED (박스권/혼조세 - 리스크 관리)"
        persona = "중립적 성향의 전략가"
        rules = """- 방향성이 불분명하므로 박스권 하단에서 매수하고 상단에서 매도하세요.
- RSI 40~45 부근 매수, RSI 65~70 부근 매도 규칙을 준수합니다.
- 불확실한 구간에서는 비중을 줄이고 짧게 끊어치는 단기 매매를 활용하세요."""
        base_pct = 35

    # ── 과거 경험 요약 (Experiences) ──────────────────────────
    exp_text = ""
    if experiences:
        successes = experiences.get("successes", [])
        failures = experiences.get("failures", [])
        
        if successes:
            exp_text += "\n### Recent Successful Decisions (Best Practices):\n"
            for s in successes:
                exp_text += f"- Decision: {s['decision']} | Reason: {s['reason']} | PnL: {s['pnl_rate']:+.2f}%\n"
        
        if failures:
            exp_text += "\n### Recent Failed Decisions (Lessons Learned):\n"
            for f in failures:
                exp_text += f"- Decision: {f['decision']} | Reason: {f['reason']} | PnL: {f['pnl_rate']:+.2f}%\n"

    system_prompt = f"""You are a quantitative trading engine for an automated system. 
Your task is to analyze market data and return a JSON object with specific fields.
Exchange: {config.SELECTED_EXCHANGE}
Market Regime: {regime}

## Strategic Rules
{rules}

## Your Past Experience (Self-Learning Data)
{exp_text if exp_text else "No experience data yet. Start learning from this cycle."}

## REQUIRED OUTPUT FORMAT (JSON ONLY, NO OTHER TEXT)
{{
  "decision": "BUY" | "SELL" | "HOLD",
  "reason": "Short technical explanation in Korean (max 2 sentences)",
  "confidence": float (0.0 to 1.0),
  "percentage": int (0 to 100)
}}

Example: {{"decision": "BUY", "reason": "RSI 과매도 및 반등 시그널 포착.", "confidence": 0.85, "percentage": 50}}"""

    user_prompt = f"""Market Data:
- Price: {current_price:,.4f} {PRICE_UNIT}
- RSI: {rsi:.1f}
- MACD Hist: {macd_hist:.4f}
- BB Position: {bb_position_pct:.1f}%
- MAs: MA5:{ma5:,.4f} / MA20:{ma20:,.4f} / MA60:{ma60:,.4f}
- Regime: {regime}

Assets:
- Value: {total_val:,.0f} KRW (Profit: {profit_rate:+.2f}%)
- Cash: {main_cash:,.2f} {PRICE_UNIT} / XRP: {xrp:.2f}

Return the JSON decision."""

    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, timeout=45.0)
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            
            # 1. Remove markdown code blocks if present
            content = re.sub(r'```json\s*|\s*```', '', content)
            
            # 2. Extract the first JSON object
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            # 3. Clean up potentially problematic characters (unescaped newlines in strings)
            # JSON doesn't allow raw newlines in strings. We'll try to replace them with \n
            # This is a bit tricky, but often AI models put actual newlines in the 'reason' field.
            def fix_json_newlines(match):
                return match.group(0).replace('\n', '\\n').replace('\r', '')
            
            # Simple regex to find content between quotes in a JSON-like structure
            content = re.sub(r'":\s*"([^"]*)"', fix_json_newlines, content)

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as je:
                print(f"JSON 파싱 1차 실패, 줄바꿈 제거 시도: {je}")
                # 극단적인 조치: 모든 실제 줄바꿈을 공백으로 치환
                try:
                    clean_content = content.replace('\n', ' ').replace('\r', ' ')
                    parsed = json.loads(clean_content)
                except Exception:
                    print("JSON 파싱 2차 실패, 정규표현식 추출 시도...")
                    # 정규표현식을 이용한 개별 필드 강제 추출 (Last Resort)
                    parsed = {}
                    dec_m = re.search(r'"decision":\s*"(BUY|SELL|HOLD)"', content, re.I)
                    if dec_m: parsed["decision"] = dec_m.group(1).upper()
                    
                    reason_m = re.search(r'"reason":\s*"([^"]*)"', content)
                    if reason_m: parsed["reason"] = reason_m.group(1)
                    
                    conf_m = re.search(r'"confidence":\s*([0-9.]+)', content)
                    if conf_m: parsed["confidence"] = conf_m.group(1)
                    
                    pct_m = re.search(r'"percentage":\s*([0-9.]+)', content)
                    if pct_m: parsed["percentage"] = pct_m.group(1)
                    
                    if not parsed.get("decision"):
                        raise ValueError("정규표현식으로도 필수 필드(decision) 추출 실패")
            
            decision = str(parsed.get("decision", "HOLD")).upper()
            if decision not in ("BUY", "SELL", "HOLD"):
                decision = "HOLD"

            return {
                "decision": decision,
                "reason": parsed.get("reason", "분석 완료"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "percentage": float(parsed.get("percentage", 0.0))
            }
    except Exception as e:
        print(f"LM Studio AI 질의 또는 파싱 최종 실패 (내부 룰 사용): {e}")
        # 오류 발생 시 텔레그램으로 즉시 알림 (중요 오류)
        from .telegram_notifier import send_telegram_message
        send_telegram_message(f"⚠️ *AI 분석 파싱 오류 발생*\n사유: `{str(e)}`\n현재 구간은 내부 룰 기반 폴백 모드로 진행합니다.")

    # ── 공격적 내부 룰 기반 폴백 AI ──────────────────────────
    macd_hist = macd.get("histogram", 0)
    macd_val = macd.get("macd", 0)
    macd_sig = macd.get("signal", 0)
    macd_golden = macd_val > macd_sig
    
    # 적극 매수: RSI 45 이하이거나, 강세장 국면에서 MACD 양수 전환 시
    if (rsi < 45 and macd_golden) or (regime.startswith("AGGRESSIVE") and macd_hist > 0):
        return {
            "decision": "BUY",
            "reason": f"RSI {rsi:.1f} 및 추세 확인. 적극적 진입으로 기회 포착.",
            "confidence": 0.85,
            "percentage": 50.0
        }
    # 단기 매수: 눌림목 판단
    elif rsi < 55 and macd_hist > -1 and bb_position_pct < 45:
        return {
            "decision": "BUY",
            "reason": "단기 눌림목 구간으로 판단되어 분할 매수 진입.",
            "confidence": 0.70,
            "percentage": 30.0
        }
    # 추세 추종 매도: RSI가 매우 높거나 꺾일 때
    elif rsi > 75 or (rsi > 65 and not macd_golden and bb_position_pct > 85):
        return {
            "decision": "SELL",
            "reason": f"RSI {rsi:.1f} 과열 및 저항선 도달. 수익 실현 후 재진입 노림.",
            "confidence": 0.80,
            "percentage": 80.0
        }
    # 관망 (범위 축소)
    else:
        return {
            "decision": "HOLD",
            "reason": "추세 확인 중. 공격적 진입을 위한 다음 타점 대기.",
            "confidence": 0.50,
            "percentage": 0.0
        }
