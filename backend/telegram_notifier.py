import asyncio
import aiohttp
import threading
from config import config

# 전역 세션 관리 (성능 및 연결 재사용)
_session = None

async def get_session():
    global _session
    if _session is None or _session.closed:
        # 연결 유지를 위한 대기 시간 및 재시도 설정
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        _session = aiohttp.ClientSession(timeout=timeout)
    return _session

async def _send_async_safe(text: str):
    """비동기 방식으로 텔레그램 메시지 발송"""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    proxy = config.TELEGRAM_PROXY if config.TELEGRAM_PROXY else None
    
    try:
        session = await get_session()
        async with session.post(url, json=payload, proxy=proxy) as response:
            if response.status != 200:
                print(f"텔레그램 메시지 전송 실패 (HTTP {response.status})")
    except Exception as e:
        print(f"텔레그램 메시지 전송 중 예외 발생: {e}")

def send_telegram_message(text: str):
    """
    비동기 스레드나 이벤트 루프에서 텔레그램 메시지 발송.
    현재 실행 중인 루프가 있으면 그 루프를 사용하고, 없으면 새로 생성함.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_send_async_safe(text))
        else:
            loop.run_until_complete(_send_async_safe(text))
    except RuntimeError:
        # 루프가 없는 스레드에서 호출된 경우
        new_loop = asyncio.new_event_loop()
        threading.Thread(target=lambda: new_loop.run_until_complete(_send_async_safe(text))).start()

async def poll_telegram_updates(on_command_cb):
    """텔레그램 메시지를 모니터링하여 특정 명령어 발생 시 콜백 실행 (개선된 비동기 및 재시도 로직)"""
    if not config.TELEGRAM_BOT_TOKEN:
        print("텔레그램 봇 토큰이 설정되지 않아 리스너를 시작하지 않습니다.")
        return

    last_update_id = 0
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    
    print("텔레그램 커맨드 리스너 시작...")
    
    retry_delay = 1
    max_retry_delay = 60

    while True:
        try:
            session = await get_session()
            params = {"offset": last_update_id + 1, "timeout": 30}
            
            proxy = config.TELEGRAM_PROXY if config.TELEGRAM_PROXY else None
            
            # 롱 폴링 (Long Polling)
            async with session.get(url, params=params, timeout=35, proxy=proxy) as response:
                if response.status == 200:
                    data = await response.json()
                    updates = data.get("result", [])
                    
                    # 성공 시 재시도 대기 시간 초기화
                    retry_delay = 1
                    
                    for update in updates:
                        last_update_id = update["update_id"]
                        message = update.get("message", {})
                        text = message.get("text", "").strip().lower()
                        chat_id = str(message.get("chat", {}).get("id", ""))

                        # 보안: 등록된 CHAT_ID만 처리
                        if chat_id == str(config.TELEGRAM_CHAT_ID):
                            if text in ["분석", "/analyze", "강제분석", "status", "/status"]:
                                if text in ["status", "/status"]:
                                    send_telegram_message("✅ *시스템 가동 중*\n현재 봇이 정상적으로 명령어를 수신하고 있습니다.")
                                    continue
                                    
                                send_telegram_message("🚀 *강제 분석 사이클 요청을 확인했습니다.* 분석을 시작합니다...")
                                await on_command_cb(is_forced=True)
                
                elif response.status == 401:
                    print("텔레그램 봇 토큰이 유효하지 않습니다. 설정을 확인해주세요.")
                    await asyncio.sleep(60)
                else:
                    print(f"텔레그램 API 서버 응답 오류 (HTTP {response.status}). {retry_delay}초 후 재시도...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)

        except aiohttp.ClientConnectorError as e:
            print(f"텔레그램 연결 오류 (네트워크 문제): {e}. {retry_delay}초 후 재시도...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
            
        except asyncio.TimeoutError:
            # 타임아웃은 롱 폴링에서 정상적인 현상일 수 있음 (조용히 재시도)
            continue
            
        except Exception as e:
            print(f"텔레그램 리스너 미확인 오류: {e}. {retry_delay}초 후 재시도...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
        
        await asyncio.sleep(0.5)
