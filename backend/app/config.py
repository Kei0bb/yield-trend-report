import os
from dotenv import load_dotenv

load_dotenv()  # backend/.env を自動読み込み


class Settings:
    # ── モード切り替え ─────────────────────────────────────────
    # .env に USE_MOCK_DATA=true  → Oracle 不要、モックデータで動作（デフォルト）
    # .env に USE_MOCK_DATA=false → 下記の Oracle 接続設定が有効になる
    USE_MOCK_DATA: bool = os.getenv("USE_MOCK_DATA", "true").lower() == "true"

    # ── Oracle DB 接続（USE_MOCK_DATA=false のときのみ使用）──────
    # oracledb は Thin モード（Pure Python）がデフォルト。
    # Oracle Instant Client のインストールは不要。
    ORACLE_DSN: str = os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1")
    ORACLE_USER: str = os.getenv("ORACLE_USER", "")
    ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "")
    ORACLE_MIN_CONNECTIONS: int = int(os.getenv("ORACLE_MIN_CONNECTIONS", "2"))
    ORACLE_MAX_CONNECTIONS: int = int(os.getenv("ORACLE_MAX_CONNECTIONS", "10"))


settings = Settings()
