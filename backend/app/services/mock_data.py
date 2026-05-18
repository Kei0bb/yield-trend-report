import random

import pandas as pd

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
    random.seed(hash(f"{product}-{process}-{start_month}") % 2**32)

    num_lots = random.randint(6, 12)
    year = int(start_month[:4])
    start_week = int(start_month[5:7]) * 4
    lots = [f"{year}W{str(start_week + i).zfill(2)}" for i in range(num_lots)]

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
            })

    return pd.DataFrame(rows, columns=COMMON_COLUMNS)
