import requests
import threading
from .config import config

def _send_async(text: str):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5.0)
    except Exception as e:
        print(f"텔레그램 메시지 전송 실패: {e}")

def send_telegram_message(text: str):
    """비동기 스레드로 텔레그램 메시지 발송 (메인 파이프라인 지연 방지)"""
    threading.Thread(target=_send_async, args=(text,), daemon=True).start()
