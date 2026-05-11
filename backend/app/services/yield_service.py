import random
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.config import settings
from app.database import get_connection, release_connection
from app.models.schemas import ProcessData

# backend/ 直下の設定ファイル
_BIN_GROUP_CSV   = Path(__file__).parent.parent.parent / "bin_group.csv"
_PRODUCT_LIST_TXT = Path(__file__).parent.parent.parent / "product_list.txt"


@lru_cache(maxsize=1)
def _load_product_list() -> list[str] | None:
    """
    product_list.txt を読み込み、表示したい PRODUCT_ID のリストを返す。
    ファイルがなければ None（= DB 全件を使用）。
    '#' で始まる行・空行はコメントとして無視。
    サーバー再起動で反映される。
    """
    if not _PRODUCT_LIST_TXT.exists():
        return None
    lines = _PRODUCT_LIST_TXT.read_text(encoding="utf-8").splitlines()
    products = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    return products if products else None


@lru_cache(maxsize=1)
def _load_bin_groups() -> dict[int, str]:
    """
    bin_group.csv を読み込み {bin_code(int): bin_group(str)} を返す。
    ファイルがなければ空辞書（= BIN_NAME をそのまま使用）。
    CSV を更新した場合はサーバー再起動で反映される。
    """
    if not _BIN_GROUP_CSV.exists():
        return {}
    df = pd.read_csv(_BIN_GROUP_CSV, dtype={"bin_code": int, "bin_group": str})
    return dict(zip(df["bin_code"], df["bin_group"]))


def _apply_bin_groups(df: pd.DataFrame) -> pd.DataFrame:
    """
    raw_bin_code(数値) を CSV のグループ名に置き換えて bin_code 列を作る。
    マッピングがない bin は bin_name をそのまま使う。
    """
    df = df.copy()
    mapping = _load_bin_groups()
    if mapping:
        # vectorized map: マッピングにない bin_code は NaN → bin_name で埋める
        df["bin_code"] = (
            df["raw_bin_code"].astype(int).map(mapping).fillna(df["bin_name"])
        )
    else:
        # CSV なし → bin_name をそのまま使用
        df["bin_code"] = df["bin_name"]
    return df


def get_products() -> list[str]:
    if settings.USE_MOCK_DATA:
        return _mock_products()

    # product_list.txt があればそのリストを返す（DB 問い合わせ不要）
    product_list = _load_product_list()
    if product_list is not None:
        return product_list

    # ファイルなし → DB から全件取得
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT PRODUCT_ID
            FROM SEMI_CP_HEADER
            WHERE DEL_FLAG = 0
            ORDER BY PRODUCT_ID
            """
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
                TO_CHAR(h.CREATE_DATE, 'IYYY"W"IW')           AS lot_id,
                h.WAFER_ID                                     AS wafer_id,
                CASE
                    WHEN h.EFFECTIVE_NUM > 0
                    THEN ROUND(h.PERFECT_PASS_CHIP / h.EFFECTIVE_NUM * 100, 3)
                    ELSE 0
                END                                            AS yield_pct,
                h.EFFECTIVE_NUM                                AS gross_die,
                b.BIN_CODE                                     AS raw_bin_code,
                b.BIN_NAME                                     AS bin_name,
                b.BIN_COUNT                                    AS bin_fail_count
            FROM SEMI_CP_HEADER h
            JOIN SEMI_CP_BIN_SUM b
              ON h.SUBSTRATE_ID = b.SUBSTRATE_ID
             AND h.WAFER_ID     = b.WAFER_ID
             AND h.PROCESS      = b.PROCESS
            WHERE h.PRODUCT_ID  = :product
              AND h.PROCESS      = :process
              AND h.CREATE_DATE >= TO_DATE(:start_month || '-01', 'YYYY-MM-DD')
              AND h.CREATE_DATE  < ADD_MONTHS(
                                      TO_DATE(:end_month || '-01', 'YYYY-MM-DD'), 1)
              AND h.DEL_FLAG     = 0
              AND b.DEL_FLAG     = 0
              AND b.BIN_QUALITY != 'PASS'
            ORDER BY TO_CHAR(h.CREATE_DATE, 'IYYY"W"IW'), h.WAFER_ID
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
            "raw_bin_code",
            "bin_name",
            "bin_fail_count",
        ]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)

        # bin_code(数値) → グループ名に置き換え
        df = _apply_bin_groups(df)

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
    # x軸は Work Week 形式（例: 2026W01）
    year = int(start_month[:4])
    start_week = int(start_month[5:7]) * 4  # 月→週の近似
    lots = [f"{year}W{str(start_week + i).zfill(2)}" for i in range(num_lots)]

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
