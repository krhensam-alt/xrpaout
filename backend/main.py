import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import mimetypes

# 윈도우 MIME 타입 버그 수정
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

from config import config
from database import init_db, get_recent_ai_reports, get_recent_trade_logs
from exchange import exchange_client
from scheduler import start_scheduler, execute_trading_cycle, register_callback
from telegram_notifier import send_telegram_message, poll_telegram_updates

# 접속된 웹소켓 클라이언트 세션 목록
websocket_clients = set()

async def broadcast_ws_message(event_type: str, data: dict):
    """모든 연결된 클라이언트에게 실시간 이벤트 전송"""
    message = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
    disconnected = set()
    for client in websocket_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)
            
    for client in disconnected:
        websocket_clients.discard(client)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB 스키마 초기화
    init_db()
    # 웹소켓 브로드캐스트 리스너 등록
    register_callback(broadcast_ws_message)
    # 백그라운드 스케줄러 구동
    scheduler_task = asyncio.create_task(start_scheduler())
    # 주기적인 실시간 시세 푸시 루프 구동
    ticker_task = asyncio.create_task(live_ticker_loop())
    # 텔레그램 명령어 리스너 구동
    telegram_task = asyncio.create_task(poll_telegram_updates(execute_trading_cycle))
    yield
    scheduler_task.cancel()
    ticker_task.cancel()
    telegram_task.cancel()

async def live_ticker_loop():
    """매 2초마다 현재가 및 자산 변동 사항을 브로드캐스팅하는 라이브 루프"""
    while True:
        await asyncio.sleep(2.0)
        if websocket_clients:
            price = exchange_client.get_current_price()
            balances = exchange_client.get_balances()
            await broadcast_ws_message("ticker", {"price": price, "balances": balances})

app = FastAPI(title="XRP AI Trading Monitor API", lifespan=lifespan)

# CORS 설정 (모바일 및 로컬 프론트엔드 접속 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def force_mime_type(request, call_next):
    response = await call_next(request)
    if request.url.path.endswith(".js"):
        response.headers["Content-Type"] = "application/javascript"
    elif request.url.path.endswith(".css"):
        response.headers["Content-Type"] = "text/css"
    return response

@app.get("/api/status")
async def get_status():
    return {
        "status": "ONLINE",
        "is_mock_mode": config.MOCK_MODE,
        "interval_minutes": config.TRADING_INTERVAL_MINUTES,
        "lm_studio_url": config.LM_STUDIO_BASE_URL,
        "current_price": exchange_client.get_current_price()
    }

@app.get("/api/asset")
async def get_asset_info():
    return exchange_client.get_balances()

@app.get("/api/reports")
async def get_reports(limit: int = 20):
    return get_recent_ai_reports(limit)

@app.get("/api/logs")
async def get_logs(limit: int = 50):
    return get_recent_trade_logs(limit)

@app.get("/api/chart")
async def get_chart_data():
    df = exchange_client.get_ohlcv(count=30)
    if df is None or df.empty:
        return []
    
    # 프론트엔드 차트 렌더링을 위한 배열 변환
    records = []
    for date, row in df.iterrows():
        records.append({
            "time": date.strftime("%H:%M") if hasattr(date, 'strftime') else str(date),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['volume'])
        })
    return records

@app.post("/api/trigger")
async def trigger_cycle():
    """수동으로 매매 사이클 즉시 기동 (데모 및 테스트용)"""
    asyncio.create_task(execute_trading_cycle())
    return {"status": "triggered", "message": "트레이딩 분석 사이클을 백그라운드에서 실행했습니다."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.add(websocket)
    try:
        # 최초 접속 시 현재 상태 즉시 푸시
        price = exchange_client.get_current_price()
        balances = exchange_client.get_balances()
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {"price": price, "balances": balances}
        }, ensure_ascii=False))
        
        while True:
            # 핑퐁 유지용 대기
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.discard(websocket)
    except Exception:
        websocket_clients.discard(websocket)

# 프론트엔드 정적 파일 서빙 (빌드된 dist 폴더)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")

    @app.get("/{rest_of_path:path}")
    async def serve_frontend(rest_of_path: str):
        # API 경로가 아닌 모든 요청은 index.html로 리다이렉트 (SPA 지원)
        if rest_of_path.startswith("api") or rest_of_path.startswith("ws"):
            return None # FastAPI가 다른 라우트를 찾도록 함
        return FileResponse(os.path.join(frontend_path, "index.html"))
