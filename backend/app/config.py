import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ORACLE_DSN: str = os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1")
    ORACLE_USER: str = os.getenv("ORACLE_USER", "")
    ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "")
    ORACLE_MIN_CONNECTIONS: int = int(os.getenv("ORACLE_MIN_CONNECTIONS", "2"))
    ORACLE_MAX_CONNECTIONS: int = int(os.getenv("ORACLE_MAX_CONNECTIONS", "10"))
    USE_MOCK_DATA: bool = os.getenv("USE_MOCK_DATA", "true").lower() == "true"


settings = Settings()
