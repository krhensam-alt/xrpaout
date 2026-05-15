import requests

token = "8816432912:AAG6xv_ieQbFHaPWVvy8MbwnfC3chnX24vo"
r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=5)
data = r.json()
updates = data.get("result", [])

if not updates:
    print("❌ 아직 메시지가 없습니다.")
    print("👉 텔레그램에서 @Osjxrpbot 봇에게 아무 메시지나 보내고 다시 실행하세요.")
else:
    print("✅ Chat ID 감지 성공!")
    for u in updates:
        if "message" in u:
            chat = u["message"]["chat"]
            print(f"   Chat ID : {chat['id']}")
            print(f"   이름    : {chat.get('first_name', '')} {chat.get('last_name', '')}")
            print(f"   유저명  : @{chat.get('username', '없음')}")
            break
