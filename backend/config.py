import os
from dotenv import load_dotenv

# .env 파일 로드 (루트 경로 기준)
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

class Config:
    UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY", "")
    UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY", "")
    BINANCE_ACCESS_KEY = os.getenv("BINANCE_ACCESS_KEY", "")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
    SELECTED_EXCHANGE = os.getenv("SELECTED_EXCHANGE", "UPBIT").upper()
    
    LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "local-model")
    TRADING_INTERVAL_MINUTES = int(os.getenv("TRADING_INTERVAL_MINUTES", "10"))
    MAX_INVESTMENT_KRW = float(os.getenv("MAX_INVESTMENT_KRW", "100000"))
    
    # 텔레그램 설정
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()
    
    # MOCK_MODE 설정 파싱
    _mock_env = os.getenv("MOCK_MODE", "True").lower()
    MOCK_MODE = _mock_env in ("true", "1", "yes", "t")

config = Config()
