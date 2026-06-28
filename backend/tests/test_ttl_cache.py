"""Tests for TTLCache (thread-safe, single-flight, LRU) and lot_service caching."""
import threading
import time
from unittest.mock import patch

import pandas as pd

from app.services.ttl_cache import TTLCache
from app.services.lot_service import _load_dataframe, clear_lot_df_cache


# ---------------------------------------------------------------------------
# TTLCache unit tests
# ---------------------------------------------------------------------------

def test_ttlcache_returns_cached_value():
    """Second call returns the cached result without invoking compute again."""
    cache = TTLCache(ttl=60)
    calls = [0]

    def compute():
        calls[0] += 1
        return "value"

    v1 = cache.get_or_compute("k", compute)
    v2 = cache.get_or_compute("k", compute)

    assert v1 == v2 == "value"
    assert calls[0] == 1, f"compute ran {calls[0]} times, expected 1"


def test_ttlcache_force_triggers_recompute():
    """force=True bypasses the cached value and recomputes."""
    cache = TTLCache(ttl=60)
    calls = [0]

    def compute():
        calls[0] += 1
        return calls[0]

    cache.get_or_compute("k", compute)
    v2 = cache.get_or_compute("k", compute, force=True)

    assert calls[0] == 2, f"expected 2 calls, got {calls[0]}"
    assert v2 == 2


def test_ttlcache_ttl_expiry_triggers_recompute():
    """With TTL=0 every value is immediately stale, so each call recomputes."""
    cache = TTLCache(ttl=0)
    calls = [0]

    def compute():
        calls[0] += 1
        return calls[0]

    v1 = cache.get_or_compute("k", compute)
    v2 = cache.get_or_compute("k", compute)

    assert calls[0] == 2, f"expected 2 calls, got {calls[0]}"
    assert v1 == 1
    assert v2 == 2


def test_ttlcache_lru_eviction():
    """LRU entry is evicted when maxsize is exceeded; MRU entries are retained."""
    cache = TTLCache(ttl=60, maxsize=2)

    cache.get_or_compute("a", lambda: "A")   # store: {a}   order: [a]
    cache.get_or_compute("b", lambda: "B")   # store: {a,b} order: [a(LRU), b(MRU)]
    cache.get_or_compute("a", lambda: "A")   # hit a → move to MRU; order: [b(LRU), a(MRU)]
    cache.get_or_compute("c", lambda: "C")   # evict b (LRU); store: {a,c}

    # "a" should still be cached — compute must NOT be called
    calls_a = [0]
    cache.get_or_compute("a", lambda: calls_a.__setitem__(0, calls_a[0] + 1) or "A")
    assert calls_a[0] == 0, "'a' should still be cached"

    # "b" should have been evicted — compute must be called once
    calls_b = [0]

    def recompute_b():
        calls_b[0] += 1
        return "B"

    cache.get_or_compute("b", recompute_b)
    assert calls_b[0] == 1, "'b' should have been evicted and recomputed"


def test_ttlcache_single_flight():
    """Multiple concurrent threads requesting the same missing key call compute() exactly once."""
    cache = TTLCache(ttl=60)
    call_count = [0]
    barrier = threading.Barrier(5)

    def compute():
        # Sleep long enough for all other threads to reach evt.wait() first
        time.sleep(0.15)
        call_count[0] += 1
        return "result"

    results = []
    results_lock = threading.Lock()

    def worker():
        barrier.wait()  # all 5 threads start simultaneously
        r = cache.get_or_compute("k", compute)
        with results_lock:
            results.append(r)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert call_count[0] == 1, f"compute() ran {call_count[0]} times, expected 1"
    assert len(results) == 5
    assert all(r == "result" for r in results)


# ---------------------------------------------------------------------------
# lot_service cache integration tests
# ---------------------------------------------------------------------------

def test_load_dataframe_cached():
    """_load_dataframe fetches the data layer only once for repeated identical calls."""
    import app.services.lot_service as ls

    original = ls.mock_lot_dataframe
    call_count = [0]

    def counting(*args, **kwargs):
        call_count[0] += 1
        return original(*args, **kwargs)

    with patch.object(ls, "mock_lot_dataframe", side_effect=counting):
        clear_lot_df_cache()  # start clean while mock is active
        df1 = _load_dataframe("Product-A", "CP", 6)
        df2 = _load_dataframe("Product-A", "CP", 6)

    assert call_count[0] == 1, f"expected 1 data-layer call, got {call_count[0]}"
    assert len(df1) > 0  # sanity: data was returned


def test_load_dataframe_returns_independent_copies():
    """Mutating the returned DataFrame must not affect the cached value or subsequent calls."""
    clear_lot_df_cache()

    df1 = _load_dataframe("Product-A", "CP", 6)
    df1["__mutated__"] = 999  # mutate the caller's copy

    df2 = _load_dataframe("Product-A", "CP", 6)
    assert "__mutated__" not in df2.columns, (
        "Mutation of a returned DataFrame must not affect the cached canonical copy"
    )
