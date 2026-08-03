import hashlib
import random
from datetime import date, timedelta

import pandas as pd

from app.services.map_queries import BIN_META_COLUMNS, DIE_COLUMNS
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
                    code = 7                         # edge ring
                elif (x - cx) ** 2 + (y - cy) ** 2 <= 2 and wrng.random() < 0.8:
                    code = 13                        # cluster
                elif wrng.random() < 0.03:
                    code = 2                         # random sprinkle
                else:
                    code = 1                         # pass
                rows.append((lot_id, wafer_id, x, y, code))
    return pd.DataFrame(rows, columns=DIE_COLUMNS)


def mock_bin_meta_dataframe(lot_id: str, process: str) -> pd.DataFrame:
    """Bin metadata mock consistent with mock_die_dataframe's bin codes:
    1=pass, 7/13/2=fail, matching the SEMI_CP_BIN_SUM lookup used in real mode."""
    rows = [
        (1, "Pass", "PASS"),
        (7, "Leakage", "FAIL"),
        (13, "VDD_Short", "FAIL"),
        (2, "Open", "FAIL"),
    ]
    return pd.DataFrame(rows, columns=BIN_META_COLUMNS)


# ---------------------------------------------------------------------------
# PCM / WAT mock
# ---------------------------------------------------------------------------

MOCK_WAT_FLAVORS: list[str] = ["RVT", "LVT", "HVT", "ULVT", "IO25", "IO18"]

WAT_DETAIL_COLUMNS = [
    "wafer_id", "site_no", "item_name", "item_unit",
    "spec_low", "spec_high", "meas_data", "start_time",
]

WAT_LOT_COLUMNS = ["lot_id", "last_measured", "wafer_count"]

# (item suffix, unit, center, spread, spec half-width) per flavor family.
# Vth centers differ per flavor so the Ion-Vt clusters separate visibly.
_WAT_VTH_CENTER = {"RVT": 0.45, "LVT": 0.32, "HVT": 0.58,
                   "ULVT": 0.24, "IO25": 0.70, "IO18": 0.62}
_WAT_IDSAT_CENTER = {"RVT": 620.0, "LVT": 780.0, "HVT": 480.0,
                     "ULVT": 880.0, "IO25": 340.0, "IO18": 400.0}

# Extra non-paired items so the summary table is not only Vth/Idsat.
# Spec margins are sized so Cpk = half_width / (3 * spread * sqrt(1 + 0.35**2))
# lands around 1.5-1.8 for these non-degraded items (the 0.35 factor accounts
# for the per-wafer bias term added on top of `spread` below).
_WAT_MISC_ITEMS = [
    ("RS_POLY", "Ohm/sq", 1040.0, 20.0, None, None),
    ("RS_NDIFF", "Ohm/sq", 78.0, 2.5, 64.0, 92.0),
    ("RS_PDIFF", "Ohm/sq", 132.0, 4.0, 111.0, 153.0),
    ("CAP_MIM", "fF/um2", 2.05, 0.04, 1.84, 2.26),
    ("VIA_CHAIN_R", "Ohm", 1.85, 0.09, 1.37, 2.33),
    ("GATE_OX_TOX", "nm", 2.20, 0.05, 1.94, 2.46),
]


def _wat_seed(*parts: str) -> int:
    return int(hashlib.md5("|".join(parts).encode()).hexdigest(), 16) % 2**32


# Generous canonical lookback for the lot timeline. Lot generation is seeded
# on product_id alone (not `months`) and always walks this full horizon, then
# `months` merely filters which lots are returned. This keeps a given lot's
# id/date reproducible regardless of which `months` value was used to reach
# it — e.g. mock_wat_dataframe re-derives lot metadata with a different
# `months` than whatever the caller used to originally list the lot.
_WAT_LOT_HORIZON_MONTHS = 36


def mock_wat_lots(product_id: str, months: int) -> pd.DataFrame:
    """Deterministic WAT lot list for a product, oldest first.

    Callers order for display; the API returns newest first.
    """
    rng = random.Random(_wat_seed("wat-lots", product_id))
    today = date.today()
    anchor = today - timedelta(days=_WAT_LOT_HORIZON_MONTHS * 30)
    cutoff = today - timedelta(days=months * 30)

    rows: list[dict] = []
    cur = anchor
    seq = 0
    while cur <= today:
        seq += 1
        if cur >= cutoff:
            rows.append({
                "lot_id": f"WAT{product_id[:4].upper()}-{cur.strftime('%y%m%d')}-{seq:03d}",
                "last_measured": cur.isoformat(),
                "wafer_count": 25,
            })
        cur += timedelta(days=rng.randint(5, 12))

    return pd.DataFrame(rows, columns=WAT_LOT_COLUMNS)


def mock_wat_dataframe(product_id: str, lot_id: str) -> pd.DataFrame:
    """Deterministic per-site WAT measurements for one lot.

    25 wafers x 9 sites x (6 flavors x 4 items + 6 misc items) = 30 items.
    Two items are deliberately degraded so the red/yellow paths render in
    mock mode: VTHN_ULVT drifts out of spec (red) and RS_NDIFF is given a
    wide spread that lands its Cpk between 1.00 and 1.33 (yellow).
    """
    lots = mock_wat_lots(product_id, _WAT_LOT_HORIZON_MONTHS)
    match = lots[lots["lot_id"] == lot_id]
    if match.empty:
        return pd.DataFrame(columns=WAT_DETAIL_COLUMNS)
    start_time = str(match["last_measured"].iloc[0])

    rng = random.Random(_wat_seed("wat-detail", product_id, lot_id))

    specs: list[tuple] = []
    for flavor in MOCK_WAT_FLAVORS:
        vc = _WAT_VTH_CENTER[flavor]
        ic = _WAT_IDSAT_CENTER[flavor]
        # Margins below give Cpk ~1.5-1.8 for non-degraded items (see the
        # sizing note above _WAT_MISC_ITEMS); VTHN_ULVT's center-shift
        # defect (below) still clears this wider Vth margin.
        specs.append((f"VTHN_{flavor}", "V", vc, 0.018, vc - 0.086, vc + 0.086))
        specs.append((f"VTHP_{flavor}", "V", -vc, 0.018, -vc - 0.086, -vc + 0.086))
        specs.append((f"IDSATN_{flavor}", "uA/um", ic, ic * 0.03, ic * 0.84, ic * 1.16))
        specs.append((f"IDSATP_{flavor}", "uA/um", ic * 0.45, ic * 0.014,
                      ic * 0.45 * 0.84, ic * 0.45 * 1.16))
    specs.extend(_WAT_MISC_ITEMS)

    rows: list[dict] = []
    for item_name, unit, center, spread, spec_low, spec_high in specs:
        # Deliberate defects so mock exercises red / yellow rendering.
        if item_name == "VTHN_ULVT":
            center += spread * 3.2       # pushes tail past the upper spec → red
        if item_name == "RS_NDIFF":
            spread *= 1.5                # widens sigma → Cpk lands in [1.00, 1.33)
        for wafer_id in range(1, 26):
            wafer_bias = rng.gauss(0, spread * 0.35)
            for site_no in range(1, 10):
                rows.append({
                    "wafer_id": wafer_id,
                    "site_no": site_no,
                    "item_name": item_name,
                    "item_unit": unit,
                    "spec_low": spec_low,
                    "spec_high": spec_high,
                    "meas_data": center + wafer_bias + rng.gauss(0, spread),
                    "start_time": start_time,
                })

    return pd.DataFrame(rows, columns=WAT_DETAIL_COLUMNS)
