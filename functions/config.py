import os
from dotenv import load_dotenv

# .env 파일 로드 (로컬 테스트용)
load_dotenv()

class Config:
    # Firebase Functions 환경 변수 또는 OS 환경 변수에서 로드
    UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY", "Um2Z4NpNinWmxgVezGr9rV9WPX7oyuOl0mLxPCYk")
    UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY", "GSABQZsZDoghRsEiOPMV359KfxbYxUWdx7xMN3c2")
    
    # LM Studio Public URL (사용자 PC 포트포워딩 주소)
    LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://112.220.123.154:13151/v1")
    LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "gemma-2-2b-it")
    
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8816432912:AAG6xv_ieQbFHaPWVvy8MbwnfC3chnX24vo")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6779572088")
    
    TRADING_INTERVAL_MINUTES = int(os.getenv("TRADING_INTERVAL_MINUTES", "60"))
    MAX_INVESTMENT_KRW = int(os.getenv("MAX_INVESTMENT_KRW", "100000"))
    MOCK_MODE = os.getenv("MOCK_MODE", "False").lower() == "true"

config = Config()
