import sqlite3
import os
import json
from datetime import datetime

# DB 파일 경로 설정 (backend 폴더 내)
DB_PATH = os.path.join(os.path.dirname(__file__), "trading_log.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 매매 로그 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            decision TEXT NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            total_krw REAL NOT NULL,
            reason TEXT
        )
    ''')
    
    # AI 의사결정 리포트 테이블 생성 (학습을 위한 성적표 필드 추가)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            decision TEXT NOT NULL,
            confidence REAL NOT NULL,
            percentage REAL NOT NULL,
            reason TEXT NOT NULL,
            indicators TEXT,
            price_at_decision REAL,
            outcome_price REAL,
            outcome_status TEXT, -- SUCCESS, FAILURE, NEUTRAL
            pnl_rate REAL
        )
    ''')
    
    conn.commit()
    conn.close()

def save_trade_log(decision: str, price: float, amount: float, total_krw: float, reason: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO trade_logs (timestamp, decision, price, amount, total_krw, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, decision, price, amount, total_krw, reason)
    )
    conn.commit()
    conn.close()

def save_ai_report(decision: str, confidence: float, percentage: float, reason: str, indicators: dict, price_at_decision: float = 0.0):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()
    indicators_str = json.dumps(indicators, ensure_ascii=False) if indicators else "{}"
    cursor.execute(
        "INSERT INTO ai_reports (timestamp, decision, confidence, percentage, reason, indicators, price_at_decision) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (now_str, decision, confidence, percentage, reason, indicators_str, price_at_decision)
    )
    conn.commit()
    conn.close()

def update_ai_report_outcome(report_id: int, outcome_price: float, outcome_status: str, pnl_rate: float):
    """사후 결과를 DB에 업데이트하여 AI 학습 데이터로 활용"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE ai_reports SET outcome_price = ?, outcome_status = ?, pnl_rate = ? WHERE id = ?",
        (outcome_price, outcome_status, pnl_rate, report_id)
    )
    conn.commit()
    conn.close()

def get_ai_experiences(limit: int = 5):
    """최근 성공 및 실패 사례를 추출하여 AI에게 지식으로 제공"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 성공 사례
    cursor.execute("SELECT * FROM ai_reports WHERE outcome_status = 'SUCCESS' ORDER BY id DESC LIMIT ?", (limit,))
    successes = [dict(row) for row in cursor.fetchall()]
    
    # 실패 사례
    cursor.execute("SELECT * FROM ai_reports WHERE outcome_status = 'FAILURE' ORDER BY id DESC LIMIT ?", (limit,))
    failures = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return {"successes": successes, "failures": failures}

def get_recent_trade_logs(limit: int = 50):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trade_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_recent_ai_reports(limit: int = 10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_reports ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
