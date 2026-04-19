import random

import pandas as pd

from app.config import settings
from app.database import get_connection, release_connection
from app.models.schemas import ProcessData


def get_products() -> list[str]:
    if settings.USE_MOCK_DATA:
        return _mock_products()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT product_name FROM wafer_test_results ORDER BY product_name"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        release_connection(conn)


def get_yield_data(
    product: str, start_month: str, end_month: str, process: str
) -> ProcessData:
    if settings.USE_MOCK_DATA:
        return _mock_yield_data(product, start_month, end_month, process)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT
                lot_id,
                wafer_id,
                yield_pct,
                gross_die,
                bin_code,
                bin_fail_count
            FROM wafer_test_results
            WHERE product_name = :product
              AND test_process = :process
              AND test_month >= :start_month
              AND test_month <= :end_month
            ORDER BY lot_id, wafer_id
        """
        cursor.execute(
            query,
            {
                "product": product,
                "process": process,
                "start_month": start_month,
                "end_month": end_month,
            },
        )

        columns = [
            "lot_id",
            "wafer_id",
            "yield_pct",
            "gross_die",
            "bin_code",
            "bin_fail_count",
        ]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)

        return _aggregate_lot_data(df)
    finally:
        release_connection(conn)


def _aggregate_lot_data(df: pd.DataFrame) -> ProcessData:
    if df.empty:
        return ProcessData(lots=[], yield_avg=[], fail_bins={})

    # Lot average yield
    yield_by_lot = df.groupby("lot_id")["yield_pct"].mean()
    lots = list(yield_by_lot.index)
    yield_avg = [round(v, 2) for v in yield_by_lot.values]

    # Bin fail % per lot: bin_fail_count / gross_die * 100
    bin_data = (
        df.groupby(["lot_id", "bin_code"])
        .agg(
            fail_sum=("bin_fail_count", "sum"),
            gross_sum=("gross_die", "sum"),
        )
        .reset_index()
    )
    bin_data["bin_pct"] = (
        bin_data["fail_sum"] / bin_data["gross_sum"] * 100
    ).round(3)

    pivot = (
        bin_data.pivot(index="lot_id", columns="bin_code", values="bin_pct")
        .fillna(0)
        .reindex(lots)
    )

    fail_bins: dict[str, list[float]] = {
        str(bin_code): [round(v, 3) for v in pivot[bin_code].values]
        for bin_code in pivot.columns
    }

    return ProcessData(lots=lots, yield_avg=yield_avg, fail_bins=fail_bins)


# --- Mock data for development ---


def _mock_products() -> list[str]:
    return ["Product-A", "Product-B", "Product-C"]


def _mock_yield_data(
    product: str, start_month: str, end_month: str, process: str
) -> ProcessData:
    random.seed(hash(f"{product}-{process}-{start_month}") % 2**32)

    num_lots = random.randint(6, 12)
    lots = [f"LOT{str(i + 1).zfill(3)}" for i in range(num_lots)]

    base_yield = {"CP": 96.0, "FT": 94.0, "SLT": 92.0}.get(process, 95.0)
    yield_avg = [round(base_yield + random.uniform(-3, 3), 2) for _ in lots]

    bin_names_map = {
        "CP": ["Bin3-Open", "Bin5-Short", "Bin7-Leak", "Bin9-Func", "Bin11-Para"],
        "FT": ["Bin3-DC", "Bin5-Func", "Bin7-Speed", "Bin9-Leak", "Bin11-Scan"],
        "SLT": ["Bin3-Boot", "Bin5-Stress", "Bin7-Perf", "Bin9-Power", "Bin11-IO"],
    }
    bin_names = bin_names_map.get(process, ["Bin3", "Bin5", "Bin7"])

    fail_bins: dict[str, list[float]] = {}
    for bin_name in bin_names:
        base_pct = random.uniform(0.1, 1.5)
        fail_bins[bin_name] = [
            round(max(0, base_pct + random.uniform(-0.3, 0.3)), 3) for _ in lots
        ]

    return ProcessData(lots=lots, yield_avg=yield_avg, fail_bins=fail_bins)
