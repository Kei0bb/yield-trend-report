import hashlib
import random
from datetime import date, timedelta

import pandas as pd

from app.services.map_queries import DIE_COLUMNS
from app.services.yield_aggregator import anchor_from_end_month, latest_iso_weeks
from app.services.yield_queries import COMMON_COLUMNS

_BIN_CODES_BY_PROCESS: dict[str, list[int]] = {
    "CP": [3, 5, 7, 9, 11],
    "FT": [2, 4, 6, 8],
    "SLT": [3, 5, 7, 9, 11],
}

_BIN_NAMES: dict[int, str] = {
    2: "DC-Fail", 3: "Open/Short", 4: "Function", 5: "Short",
    6: "Speed", 7: "Leak", 8: "Power", 9: "Functional", 11: "Parametric",
}

_BASE_YIELD: dict[str, float] = {"CP": 96.0, "FT": 94.0, "SLT": 92.0}


def mock_products() -> list[str]:
    return ["Product-A", "Product-B", "Product-C"]


def mock_yield_dataframe(product: str, start_month: str, end_month: str, process: str) -> pd.DataFrame:
    """Generate a mock DataFrame with the same shape as the real DB query result.

    Uses a deterministic seed so the same inputs always produce the same data,
    making it easier to test UI behaviour reproducibly.
    Bin mapping CSVs are applied downstream (as with real data), so they work in mock mode too.
    """
    random.seed(hash(f"{product}-{process}-{end_month}") % 2**32)
    lots = latest_iso_weeks(anchor_from_end_month(end_month), 12)

    base_yield = _BASE_YIELD.get(process, 95.0)
    bin_codes = _BIN_CODES_BY_PROCESS.get(process, [3, 5, 7])

    rows = []
    for lot_id in lots:
        wafer_yield = round(base_yield + random.uniform(-3, 3), 2)
        gross_die = random.randint(800, 1200)
        for bin_code in bin_codes:
            fail_count = max(0, int(gross_die * random.uniform(0.001, 0.015)))
            rows.append({
                "lot_id": lot_id,
                "wafer_id": 1,
                "yield_pct": wafer_yield,
                "gross_die": gross_die,
                "raw_bin_code": bin_code,
                "bin_name": _BIN_NAMES.get(bin_code, f"Bin{bin_code}"),
                "bin_fail_count": fail_count,
                "substrate_id": "MOCK1",
            })

    return pd.DataFrame(rows, columns=COMMON_COLUMNS)


def mock_lot_dataframe(product: str, process: str, months: int = 6) -> pd.DataFrame:
    """Generate lot-granular mock data (multiple lots per week) for Dashboard/Explore.

    Deterministic per (product, process, months) — seeded via a stable hash so
    the same inputs reproduce across process restarts. Columns superset
    COMMON_COLUMNS with an added 'lot_date' (ISO string). The newest lot of each
    series gets a deliberate yield dip + bin spike so anomaly detection is
    exercised in mock mode.
    """
    key = f"lot-{product}-{process}-{months}"
    random.seed(int(hashlib.md5(key.encode()).hexdigest(), 16) % 2**32)
    base_yield = _BASE_YIELD.get(process, 95.0)
    bin_codes = _BIN_CODES_BY_PROCESS.get(process, [3, 5, 7])

    today = date.today()
    start = today - timedelta(days=months * 30)

    rows: list[dict] = []
    seq = 0
    cur = start
    all_dates: list[date] = []
    while cur <= today:
        for _ in range(random.randint(1, 3)):
            all_dates.append(cur)
        cur += timedelta(weeks=1)

    for i, lot_date in enumerate(all_dates):
        seq += 1
        is_latest = i == len(all_dates) - 1
        wafer_yield = round(base_yield + random.uniform(-2, 2), 2)
        if is_latest:
            wafer_yield = round(base_yield - 6.0, 2)
        lot_id = f"{product[:4].upper()}-{lot_date.strftime('%Y%m%d')}-{seq:03d}"
        for wafer_id in range(1, random.randint(3, 6)):
            gross_die = random.randint(800, 1200)
            for bin_code in bin_codes:
                rate = random.uniform(0.001, 0.012)
                if is_latest and bin_code == bin_codes[0]:
                    rate *= 4.0
                fail_count = max(0, int(gross_die * rate))
                rows.append({
                    "lot_id": lot_id,
                    "lot_date": lot_date.isoformat(),
                    "wafer_id": wafer_id,
                    "yield_pct": wafer_yield,
                    "gross_die": gross_die,
                    "raw_bin_code": bin_code,
                    "bin_name": _BIN_NAMES.get(bin_code, f"Bin{bin_code}"),
                    "bin_fail_count": fail_count,
                    "test_program_rev": "REV01",
                })

    columns = COMMON_COLUMNS + ["lot_date", "test_program_rev"]
    return pd.DataFrame(rows, columns=columns)


def mock_die_dataframe(lot_id: str, process: str) -> pd.DataFrame:
    """Deterministic per-die mock for the Wafer Map tab.

    Circle of radius 8 (~200 die), integer grid centered on (0, 0).
    Per wafer: mostly PASS (bin 1) + an edge ring of bin 7, one cluster of
    bin 13, and a sprinkle of bin 2 — enough structure to eyeball edge/cluster
    patterns in the UI.

    Uses local `random.Random(seed_string)` instances (not the module-level
    `random.seed()` used elsewhere in this file) so this generator neither
    disturbs nor is disturbed by other mock functions' global RNG state.
    """
    wafer_count = 25  # 1ロット=25枚固定（FOUP満載）
    rows: list[tuple] = []
    for w in range(1, wafer_count + 1):
        wafer_id = str(w)
        wrng = random.Random(f"{lot_id}|{process}|{w}")
        # one defect cluster center per wafer
        cx, cy = wrng.randint(-5, 5), wrng.randint(-5, 5)
        for y in range(-8, 9):
            for x in range(-8, 9):
                r2 = x * x + y * y
                if r2 > 64:
                    continue
                if r2 >= 49 and wrng.random() < 0.35:
                    code, quality = 7, "FAIL"        # edge ring
                elif (x - cx) ** 2 + (y - cy) ** 2 <= 2 and wrng.random() < 0.8:
                    code, quality = 13, "FAIL"       # cluster
                elif wrng.random() < 0.03:
                    code, quality = 2, "FAIL"        # random sprinkle
                else:
                    code, quality = 1, "PASS"
                rows.append((lot_id, wafer_id, x, y, code, quality))
    return pd.DataFrame(rows, columns=DIE_COLUMNS)
