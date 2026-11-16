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
    
    LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://192.168.0.37:8000/v1")
    LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen2.5-coder-32b-vllm")
    LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "vllm-local-key")
    TRADING_INTERVAL_MINUTES = int(os.getenv("TRADING_INTERVAL_MINUTES", "60"))
    MAX_INVESTMENT_KRW = float(os.getenv("MAX_INVESTMENT_KRW", "100000"))
    
    # 전략 파라미터 (1시간봉 돌파 추세추종, 2024-11 ~ 2026-10 백테스트로 검증)
    STRATEGY_INTERVAL = os.getenv("STRATEGY_INTERVAL", "minute60")
    BREAKOUT_PERIOD = int(os.getenv("BREAKOUT_PERIOD", "55"))        # 직전 N봉 고가 돌파 시 진입
    TREND_EMA_PERIOD = int(os.getenv("TREND_EMA_PERIOD", "200"))     # 종가가 EMA 위일 때만 진입, 아래로 마감하면 청산
    ATR_STOP_MULT = float(os.getenv("ATR_STOP_MULT", "3.0"))         # 초기 손절: 진입가 - N*ATR
    ATR_TRAIL_MULT = float(os.getenv("ATR_TRAIL_MULT", "4.0"))       # 트레일링: 보유 중 최고가 - N*ATR
    RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "2.0"))  # 1회 손절 시 최대 손실 (가용 현금 대비 %)
    DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "4.0"))
    LLM_VETO_ENABLED = os.getenv("LLM_VETO_ENABLED", "True").lower() in ("true", "1", "yes", "t")

    # 텔레그램 설정
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()
    
    # 영구 저장소 경로 (K8s 연동)
    DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "trading_log.db"))
    STATE_PATH = os.getenv("STATE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "trading_state.json"))
    
    # MOCK_MODE 설정 파싱
    _mock_env = os.getenv("MOCK_MODE", "True").lower()
    MOCK_MODE = _mock_env in ("true", "1", "yes", "t")

config = Config()
