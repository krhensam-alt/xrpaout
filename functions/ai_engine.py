import requests
import json
import re
from .config import config

def query_ai_decision(indicators: dict, balances: dict) -> dict:
    """LM Studio REST API를 통해 의사결정 질의 (1시간봉 전략 최적화)"""
    url = f"{config.LM_STUDIO_BASE_URL.rstrip('/')}/chat/completions"

    current_price = indicators.get("current_price", 0)
    rsi = indicators.get("rsi_14", 50)
    macd = indicators.get("macd", {})
    bb = indicators.get("bollinger", {})
    ma = indicators.get("ma", {})
    krw = balances.get("krw", 0)
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

    # 이동평균선 정배열/역배열 판단
    ma5 = ma.get("ma5", current_price)
    ma20 = ma.get("ma20", current_price)
    ma60 = ma.get("ma60", current_price)
    trend = "정배열(상승 추세)" if ma5 > ma20 > ma60 else ("역배열(하락 추세)" if ma5 < ma20 < ma60 else "혼조세")

    system_prompt = """당신은 10년 경력의 암호화폐 퀀트 트레이더입니다.
1시간봉 데이터를 기반으로 XRP 단기 매매 판단을 내립니다.

## 판단 원칙
- 수익 보다 자산 보존이 우선입니다. 불확실할 때는 반드시 HOLD.
- 수수료(0.05%)를 고려하여 최소 +1% 이상 기대 수익이 있을 때만 매수 권장.
- RSI 30 이하 + MACD 골든크로스 + 볼린저 하단 근접: 강력 매수 시그널.
- RSI 70 이상 + MACD 데드크로스 + 볼린저 상단 근접: 강력 매도 시그널.
- 이동평균선 역배열 + RSI 50 이상: 매수 금지.
- 보유 포지션이 있을 때 익절/손절은 별도 로직이 담당하므로, 신규 진입 타점에만 집중.
- 잔고가 부족하더라도(보유 KRW가 적더라도), 기술 지표상 매수 타점이라고 판단되면 'BUY' 결정을 내리십시오. 잔고 제약은 시스템 코드가 처리하므로, 오직 차트 지표 관점의 분석 이유를 reason에 작성하세요.

## 응답 형식 (반드시 아래 JSON만 출력, 다른 텍스트 절대 금지)
{"decision": "BUY", "reason": "핵심 근거 요약 (한국어, 2문장 이내)", "confidence": 0.85, "percentage": 30}"""

    user_prompt = f"""## 현재 XRP 1시간봉 시장 지표

| 지표 | 값 |
|------|-----|
| 현재가 | {current_price:,.1f} KRW |
| RSI(14) | {rsi:.1f} |
| MACD | {macd.get('macd', 0):.4f} |
| MACD Signal | {macd.get('signal', 0):.4f} |
| MACD 히스토그램 | {macd.get('histogram', 0):.4f} |
| 볼린저 상단 | {bb_upper:,.1f} |
| 볼린저 중단(MA20) | {bb_mid:,.1f} |
| 볼린저 하단 | {bb_lower:,.1f} |
| 볼린저 위치 | {bb_position_pct:.1f}% (0%=하단, 100%=상단) |
| MA5 | {ma5:,.1f} |
| MA20 | {ma20:,.1f} |
| MA60 | {ma60:,.1f} |
| 이동평균 배열 | {trend} |

## 현재 보유 자산
| 항목 | 값 |
|------|-----|
| 보유 KRW | {krw:,.0f} 원 |
| 보유 XRP | {xrp:.4f} XRP |
| XRP 매수 평단가 | {avg_buy:,.1f} KRW |
| 현재 평가 손익률 | {profit_rate:+.2f}% |
| 총 평가 자산 | {total_val:,.0f} 원 |

위 데이터를 기반으로 최선의 매매 결정을 JSON으로만 반환하세요."""

    payload = {
        "model": config.LM_STUDIO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,   # 낮은 temperature로 일관된 판단 유도
        "max_tokens": 200,
        "stream": False
    }

    fallback_res = {
        "decision": "HOLD",
        "reason": "AI 서버 응답 지연 또는 연결 실패. 안전을 위해 관망 유지.",
        "confidence": 0.5,
        "percentage": 0.0
    }

    try:
        response = requests.post(url, json=payload, timeout=15.0)
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            
            # JSON 블록 추출 (마크다운 코드블록 포함 대응)
            json_match = re.search(r'\{[^{}]*"decision"[^{}]*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
            else:
                parsed = json.loads(content)
                
            decision = parsed.get("decision", "HOLD").upper()
            if decision not in ("BUY", "SELL", "HOLD"):
                decision = "HOLD"

            return {
                "decision": decision,
                "reason": parsed.get("reason", "분석 이유 누락"),
                "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.5)))),
                "percentage": max(0.0, min(100.0, float(parsed.get("percentage", 0.0))))
            }
    except Exception as e:
        print(f"LM Studio AI 질의 실패, 내부 룰 기반 판단으로 대체: {e}")

    # ── 내부 룰 기반 폴백 AI (1시간봉 최적화 버전) ──────────────────────────
    macd_hist = macd.get("histogram", 0)
    macd_val = macd.get("macd", 0)
    macd_sig = macd.get("signal", 0)
    macd_golden = macd_val > macd_sig  # 골든크로스 여부

    # 강력 매수: RSI 과매도 + MACD 골든크로스 + 볼린저 하단 근접
    if rsi < 32 and macd_golden and bb_position_pct < 20:
        return {
            "decision": "BUY",
            "reason": f"RSI {rsi:.1f} 과매도+MACD 골든크로스+볼린저 하단({bb_position_pct:.0f}%) 위치. 반등 강력 시그널.",
            "confidence": 0.88,
            "percentage": 40.0
        }
    # 매수: RSI 과매도 + MACD 반등
    elif rsi < 38 and macd_hist > 0 and trend != "역배열(하락 추세)":
        return {
            "decision": "BUY",
            "reason": f"RSI {rsi:.1f} 과매도 구간이며 MACD 히스토그램 반등 포착. 분할 매수 진입 타점.",
            "confidence": 0.75,
            "percentage": 25.0
        }
    # 강력 매도: RSI 과매수 + MACD 데드크로스 + 볼린저 상단 근접
    elif rsi > 68 and not macd_golden and bb_position_pct > 80:
        return {
            "decision": "SELL",
            "reason": f"RSI {rsi:.1f} 과매수+MACD 데드크로스+볼린저 상단({bb_position_pct:.0f}%) 위치. 조정 하락 위험.",
            "confidence": 0.82,
            "percentage": 60.0
        }
    # 매도: RSI 과매수
    elif rsi > 72:
        return {
            "decision": "SELL",
            "reason": f"RSI {rsi:.1f} 과매수 구간. 단기 조정을 대비하여 일부 수익 실현 권장.",
            "confidence": 0.70,
            "percentage": 40.0
        }
    # 관망
    else:
        return {
            "decision": "HOLD",
            "reason": f"RSI {rsi:.1f}, {trend}. 현재 명확한 방향성 시그널 없음. 다음 캔들 대기.",
            "confidence": 0.62,
            "percentage": 0.0
        }
