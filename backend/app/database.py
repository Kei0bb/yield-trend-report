import oracledb

from app.config import settings

pool: oracledb.ConnectionPool | None = None


def init_pool() -> None:
    global pool
    if settings.USE_MOCK_DATA:
        return
    pool = oracledb.create_pool(
        user=settings.ORACLE_USER,
        password=settings.ORACLE_PASSWORD,
        dsn=settings.ORACLE_DSN,
        min=settings.ORACLE_MIN_CONNECTIONS,
        max=settings.ORACLE_MAX_CONNECTIONS,
        increment=1,
    )


def get_connection():
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool.acquire()


def release_connection(conn) -> None:
    if pool is not None:
        pool.release(conn)


def close_pool() -> None:
    global pool
    if pool is not None:
        pool.close()
        pool = None
