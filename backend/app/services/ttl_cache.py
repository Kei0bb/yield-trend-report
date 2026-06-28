"""Tiny in-process TTL cache for expensive DB-backed responses.

Lazy: a value is (re)computed only when missing, stale, or force=True.
``TTLCache`` is thread-safe and single-flight: when multiple threads request
the same missing/stale key only one runs compute(); the others wait and share
the result.  For multi-worker deployments replace with an external store
(Redis) — this cache is per-process only."""
import collections
import logging
import threading
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


class TTLCache:
    """Thread-safe, single-flight, LRU-evicting TTL cache.

    Only one thread runs compute() per key; others wait and share the result.
    For multi-worker deployments, replace with a shared external store (Redis).
    """

    def __init__(self, *, ttl: float = DEFAULT_TTL_SECONDS, maxsize: int = 64):
        self._ttl = ttl
        self._maxsize = maxsize
        self._store: collections.OrderedDict[str, tuple[float, object]] = collections.OrderedDict()
        self._lock = threading.Lock()
        self._inflight: dict[str, threading.Event] = {}

    def get_or_compute(self, key: str, compute: Callable[[], object], *, force: bool = False) -> object:
        _force = force
        while True:
            with self._lock:
                if not _force and key in self._store:
                    ts, val = self._store[key]
                    now = time.time()
                    if now - ts < self._ttl:
                        self._store.move_to_end(key)
                        logger.debug("cache hit %s (age %.0fs)", key, now - ts)
                        return val
                # Stale or missing; check if another thread is already computing
                if key in self._inflight:
                    evt = self._inflight[key]
                    am_computing = False
                else:
                    evt = threading.Event()
                    self._inflight[key] = evt
                    am_computing = True

            if not am_computing:
                # Wait without holding the lock; then loop to re-check cache
                evt.wait()
                _force = False
                continue

            # This thread owns compute() — global lock is NOT held during the call
            try:
                val = compute()
                with self._lock:
                    if key not in self._store and len(self._store) >= self._maxsize:
                        oldest, _ = self._store.popitem(last=False)
                        logger.debug("cache evict %s", oldest)
                    self._store[key] = (time.time(), val)
                    self._store.move_to_end(key)
                logger.info("cache fill %s (force=%s)", key, _force)
                return val
            finally:
                # Signal waiters whether compute succeeded or raised
                with self._lock:
                    self._inflight.pop(key, None)
                evt.set()

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            for evt in self._inflight.values():
                evt.set()
            self._inflight.clear()
