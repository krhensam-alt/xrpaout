import sqlite3
import os

# DB 파일 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "trading_log.db")

def migrate():
    print(f"Connecting to {DB_PATH} for migration...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 추가할 컬럼 목록
    new_columns = [
        ("price_at_decision", "REAL"),
        ("outcome_price", "REAL"),
        ("outcome_status", "TEXT"),
        ("pnl_rate", "REAL")
    ]
    
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE ai_reports ADD COLUMN {col_name} {col_type}")
            print(f"Column '{col_name}' added successfully.")
        except sqlite3.OperationalError:
            print(f"Column '{col_name}' already exists. Skipping.")
            
    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
