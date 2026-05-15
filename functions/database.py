import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import json
import os

# Firebase Admin SDK 초기화
# 파이러베이스 함수 환경에서는 자동으로 인증되지만, 로컬 테스트를 위해 예외 처리
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

def save_trade_log(decision: str, price: float, amount: float, total_krw: float, reason: str):
    """매매 로그를 Firestore에 저장"""
    doc_ref = db.collection('trade_logs').document()
    doc_ref.set({
        'timestamp': datetime.now().isoformat(),
        'decision': decision,
        'price': price,
        'amount': amount,
        'total_krw': total_krw,
        'reason': reason
    })

def save_ai_report(decision: str, confidence: float, percentage: float, reason: str, indicators: dict):
    """AI 분석 리포트를 Firestore에 저장"""
    doc_ref = db.collection('ai_reports').document()
    doc_ref.set({
        'timestamp': datetime.now().isoformat(),
        'decision': decision,
        'confidence': confidence,
        'percentage': percentage,
        'reason': reason,
        'indicators': json.dumps(indicators, ensure_ascii=False) if indicators else "{}"
    })

def get_recent_trade_logs(limit: int = 50):
    """최근 매매 로그 조회"""
    docs = db.collection('trade_logs').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()
    return [doc.to_dict() for doc in docs]

def get_recent_ai_reports(limit: int = 10):
    """최근 AI 리포트 조회"""
    docs = db.collection('ai_reports').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()
    return [doc.to_dict() for doc in docs]
