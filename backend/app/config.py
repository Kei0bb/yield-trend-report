from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Mock mode (default true: Oracle not required)
    USE_MOCK_DATA: bool = True

    # Oracle DB connection (used when USE_MOCK_DATA=false)
    ORACLE_DSN: str = "localhost:1521/XEPDB1"
    ORACLE_USER: str = ""
    ORACLE_PASSWORD: str = ""
    ORACLE_MIN_CONNECTIONS: int = 2
    ORACLE_MAX_CONNECTIONS: int = 10

    # Log level: DEBUG / INFO / WARNING / ERROR
    LOG_LEVEL: str = "INFO"

    # CORS allowed origins (comma-separated string or JSON list in .env)
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def validate_db_config(self) -> None:
        if not self.USE_MOCK_DATA and not (self.ORACLE_USER and self.ORACLE_PASSWORD):
            raise ValueError(
                "ORACLE_USER and ORACLE_PASSWORD are required when USE_MOCK_DATA=false. "
                "Set them in backend/.env"
            )


settings = Settings()
