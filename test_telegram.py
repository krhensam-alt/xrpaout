import requests

token = "8816432912:AAG6xv_ieQbFHaPWVvy8MbwnfC3chnX24vo"
chat_id = "6779572088"

msg = (
    "✅ *XRP AI 자동 매매 시스템 연동 완료!*\n\n"
    "📊 앞으로 아래 알림을 이 채팅으로 받아보실 수 있습니다:\n\n"
    "• 🧠 AI 분석 리포트 (매 60분 주기)\n"
    "• ⚡ 자동 매수/매도 체결 완료 알림\n"
    "• 🎉 익절매 집행 알림 (+2.5% 달성 시)\n"
    "• 🚨 손절매 집행 알림 (-3.5% 하락 시)\n\n"
    "_XRP 1시간봉 기반 퀀트 전략으로 자산을 운용합니다._"
)

r = requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
    timeout=5
)
if r.status_code == 200:
    print("✅ 텔레그램 테스트 메시지 발송 성공!")
else:
    print(f"❌ 발송 실패: {r.text}")
