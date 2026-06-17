"""Tiny in-process TTL cache for expensive DB-backed responses.

Lazy: a value is (re)computed only when missing, stale, or force=True.
Single-process uvicorn assumed (the app runs one worker)."""
import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 3 * 60 * 60  # 3 hours

_store: dict[str, tuple[float, object]] = {}


def get_or_compute(key: str, compute: Callable[[], object], *, force: bool = False,
                   ttl: float = DEFAULT_TTL_SECONDS) -> object:
    now = time.time()
    if not force and key in _store:
        ts, val = _store[key]
        if now - ts < ttl:
            logger.debug("cache hit %s (age %.0fs)", key, now - ts)
            return val
    val = compute()
    _store[key] = (now, val)
    logger.info("cache fill %s (force=%s)", key, force)
    return val
