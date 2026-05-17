import random
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.config import settings
from app.database import get_connection, release_connection
from app.models.schemas import ProcessData

# backend/ 直下の設定ファイル
_BACKEND_ROOT        = Path(__file__).parent.parent.parent
_BIN_MAPPINGS_DIR    = _BACKEND_ROOT / "bin_mappings"          # 製品別 bin マッピングディレクトリ
_BIN_GROUP_CSV       = _BACKEND_ROOT / "bin_group.csv"          # 旧フォーマット (フォールバック用)
_PRODUCT_LIST_TXT    = _BACKEND_ROOT / "product_list.txt"
_PRODUCT_CONFIG_CSV  = _BACKEND_ROOT / "product_config.csv"

# bin_group 未指定時のデフォルト識別子
_DEFAULT_BIN_GROUP = "default"
# process 未指定のワイルドカード
_ANY_PROCESS = "*"


# ──────────────────────────────────────────────────────────────────────
# Product 設定 (nickname ↔ CP/FT PRODUCT_ID マッピング)
# ──────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_product_config() -> dict[str, dict[str, str]] | None:
    """
    product_config.csv を読み込み {nickname: {cp_product_id, ft_product_id, bin_group}} を返す。
    ファイルがなければ None (= product_list.txt にフォールバック)。

    CSV フォーマット:
        nickname,cp_product_id,ft_product_id,bin_group
        Product-A,P12345-A,Q67890-A,main
    """
    if not _PRODUCT_CONFIG_CSV.exists():
        return None

    df = pd.read_csv(_PRODUCT_CONFIG_CSV, dtype=str, comment="#").fillna("")
    if "nickname" not in df.columns:
        return None

    config: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        nickname = row["nickname"].strip()
        if not nickname or nickname.startswith("#"):
            continue
        config[nickname] = {
            "display_name": row.get("display_name", "").strip() or nickname,
            "cp_product_id": row.get("cp_product_id", "").strip(),
            "ft_product_id": row.get("ft_product_id", "").strip(),
            "bin_group": row.get("bin_group", "").strip() or _DEFAULT_BIN_GROUP,
        }
    return config if config else None


def _resolve_product_id(nickname: str, process: str) -> str:
    """
    nickname と process から DB クエリ用の PRODUCT_ID を解決する。
    product_config.csv がない場合は nickname をそのまま PRODUCT_ID として使用。
    """
    config = _load_product_config()
    if config is None or nickname not in config:
        return nickname
    key = f"{process.lower()}_product_id"
    return config[nickname].get(key, "") or nickname


def _resolve_bin_group(nickname: str) -> str:
    """nickname から bin_group 識別子を解決。なければデフォルト。"""
    config = _load_product_config()
    if config is None or nickname not in config:
        return _DEFAULT_BIN_GROUP
    return config[nickname].get("bin_group", _DEFAULT_BIN_GROUP)


def resolve_display_name(nickname: str) -> str:
    """nickname から display_name を解決。未設定なら nickname そのもの。"""
    config = _load_product_config()
    if config is None or nickname not in config:
        return nickname
    return config[nickname].get("display_name", nickname)


def group_by_display_name(nicknames: list[str]) -> dict[str, list[str]]:
    """
    nickname のリストを display_name でグループ化。
    {display_name: [nicknames...]} を返す (順序は入力順に保つ)。
    """
    groups: dict[str, list[str]] = {}
    for nickname in nicknames:
        display = resolve_display_name(nickname)
        groups.setdefault(display, []).append(nickname)
    return groups


@lru_cache(maxsize=1)
def _load_product_list() -> list[str] | None:
    """
    product_list.txt を読み込み、表示したい PRODUCT_ID のリストを返す。
    ファイルがなければ None（= DB 全件を使用）。
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


# ──────────────────────────────────────────────────────────────────────
# Bin マッピング (製品ごとに別 CSV ファイル)
#   bin_mappings/<bin_group>.csv を読み込んで {process: {bin_code: bin_group_name}} を返す
# ──────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=32)
def _load_bin_mapping(bin_group: str) -> dict[str, dict[int, str]]:
    """
    bin_mappings/<bin_group>.csv を読み込み {process: {bin_code: bin_group_name}} を返す。
    ファイルがなければ空辞書 → _apply_bin_groups で BIN_NAME にフォールバック。

    CSV フォーマット (process 列ありの場合: process 別マッピング):
        process,bin_code,bin_group_name
        CP,3,Open/Short
        FT,2,DC-Fail

    CSV フォーマット (process 列なしの場合: 全 process 共通):
        bin_code,bin_group_name
        3,Open/Short
    """
    if not bin_group:
        return {}

    csv_path = _BIN_MAPPINGS_DIR / f"{bin_group}.csv"
    if not csv_path.exists():
        # 旧フォーマット (backend/bin_group.csv) フォールバック
        if bin_group == _DEFAULT_BIN_GROUP:
            return _load_legacy_bin_groups()
        return {}

    df = pd.read_csv(csv_path, dtype=str, comment="#").fillna("")
    if df.empty or "bin_code" not in df.columns or "bin_group_name" not in df.columns:
        return {}

    result: dict[str, dict[int, str]] = {}
    has_process_col = "process" in df.columns
    for _, row in df.iterrows():
        code = row.get("bin_code", "").strip()
        name = row.get("bin_group_name", "").strip()
        if not code or not name:
            continue
        proc = (row.get("process", "").strip().upper() if has_process_col else "") or _ANY_PROCESS
        result.setdefault(proc, {})[int(code)] = name
    return result


def _load_legacy_bin_groups() -> dict[str, dict[int, str]]:
    """
    旧 backend/bin_group.csv (bin_code,bin_group のみ) を読み込み、
    {'*': {bin_code: bin_group_name}} 形式で返す (後方互換)。
    """
    if not _BIN_GROUP_CSV.exists():
        return {}
    df = pd.read_csv(_BIN_GROUP_CSV, dtype=str, comment="#").fillna("")
    if df.empty or "bin_code" not in df.columns:
        return {}
    name_col = "bin_group_name" if "bin_group_name" in df.columns else "bin_group"
    if name_col not in df.columns:
        return {}
    mapping = {}
    for _, row in df.iterrows():
        code = row["bin_code"].strip()
        name = row[name_col].strip()
        if code and name:
            mapping[int(code)] = name
    return {_ANY_PROCESS: mapping} if mapping else {}


def _apply_bin_groups(
    df: pd.DataFrame, bin_group: str = _DEFAULT_BIN_GROUP, process: str = _ANY_PROCESS
) -> pd.DataFrame:
    """
    raw_bin_code(数値) を bin_mappings/<bin_group>.csv のグループ名に置き換えて
    bin_code 列を作る。マッピング検索順:
        1. <bin_group>.csv の process 完全一致
        2. <bin_group>.csv の '*' (process 列なし行)
    マッピングがない bin は DB の BIN_NAME をそのまま使用。
    """
    df = df.copy()
    proc_mappings = _load_bin_mapping(bin_group)
    proc_key = (process or _ANY_PROCESS).upper()

    mapping: dict[int, str] = {}
    # 優先順位: process 完全一致 > ワイルドカード '*'
    for key in (proc_key, _ANY_PROCESS):
        if key in proc_mappings:
            for code, name in proc_mappings[key].items():
                mapping.setdefault(code, name)

    if mapping:
        df["bin_code"] = (
            df["raw_bin_code"].astype(int).map(mapping).fillna(df["bin_name"])
        )
    else:
        df["bin_code"] = df["bin_name"]
    return df


def get_products() -> list[str]:
    """
    UI に表示する品種リストを返す。
    優先度:
        1. product_config.csv の nickname (CP/FT 別 PRODUCT_ID 対応)
        2. product_list.txt のリスト
        3. DB の SEMI_CP_HEADER.PRODUCT_ID 全件 (mock 時はモック品種)
    """
    # product_config.csv は mock / 本番ともに優先 (nickname テストのため)
    config = _load_product_config()
    if config is not None:
        return list(config.keys())

    if settings.USE_MOCK_DATA:
        return _mock_products()

    # 優先2: product_list.txt
    product_list = _load_product_list()
    if product_list is not None:
        return product_list

    # 優先3: DB 全件
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


# 共通カラム順（CP / FT 両方の SELECT 結果がこの順で出る）
_COMMON_COLUMNS = [
    "lot_id",
    "wafer_id",
    "yield_pct",
    "gross_die",
    "raw_bin_code",
    "bin_name",
    "bin_fail_count",
]


def get_yield_data(
    product: str, start_month: str, end_month: str, process: str
) -> ProcessData:
    """単一 nickname の yield データ取得。後方互換用に残置。"""
    return get_yield_data_merged([product], start_month, end_month, process)


def get_yield_data_merged(
    nicknames: list[str], start_month: str, end_month: str, process: str
) -> ProcessData:
    """
    複数 nickname を同一品種としてマージしたデータを返す。
    主に改版品種（同じ display_name を持つ複数 nickname）の統合用。
    各 nickname の DataFrame を concat した後に集計するため、
    work week が重複していれば自動的に平均/合算される。
    """
    if not nicknames:
        return ProcessData(lots=[], yield_avg=[], fail_bins={})

    if settings.USE_MOCK_DATA:
        # mock では display_name をシードにしてマージ後の見え方を再現
        display = resolve_display_name(nicknames[0])
        return _mock_yield_data(display, start_month, end_month, process)

    # 各 nickname を DB クエリして DataFrame を蓄積
    dfs: list[pd.DataFrame] = []
    for nickname in nicknames:
        real_product_id = _resolve_product_id(nickname, process)
        if not real_product_id:
            continue
        if process == "CP":
            df = _query_cp(real_product_id, start_month, end_month, process)
        elif process == "FT":
            df = _query_ft(real_product_id, start_month, end_month, process)
        else:
            # SLT 等、未実装の工程
            continue
        if not df.empty:
            dfs.append(df)

    if not dfs:
        return ProcessData(lots=[], yield_avg=[], fail_bins={})

    combined = pd.concat(dfs, ignore_index=True)
    # 改版品種は同じ bin_group を共有する前提。最初の nickname のグループを採用。
    bin_group = _resolve_bin_group(nicknames[0])
    combined = _apply_bin_groups(combined, bin_group=bin_group, process=process)
    return _aggregate_lot_data(combined)


def _query_cp(
    product: str, start_month: str, end_month: str, process: str
) -> pd.DataFrame:
    """CP: SEMI_CP_BIN_SUM は集計済みなので BIN_COUNT をそのまま使用"""
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
    return _execute_query(
        query,
        {
            "product": product,
            "process": process,
            "start_month": start_month,
            "end_month": end_month,
        },
    )


def _query_ft(
    product: str, start_month: str, end_month: str, process: str
) -> pd.DataFrame:
    """
    FT: SEMI_FT_BIN_SUM は CP と同じく集計済みのため BIN_COUNT をそのまま使用。
    CP との違いは：
      - テーブル名が SEMI_FT_HEADER / SEMI_FT_BIN_SUM
      - FT は ASSY_LOT_ID を持つため JOIN キーに含める
    """
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
        FROM SEMI_FT_HEADER h
        JOIN SEMI_FT_BIN_SUM b
          ON h.SUBSTRATE_ID = b.SUBSTRATE_ID
         AND h.ASSY_LOT_ID  = b.ASSY_LOT_ID
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
    return _execute_query(
        query,
        {
            "product": product,
            "process": process,
            "start_month": start_month,
            "end_month": end_month,
        },
    )


def _execute_query(query: str, params: dict) -> pd.DataFrame:
    """CP / FT 共通の実行ヘルパー。結果を pandas DataFrame に変換して返す。"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=_COMMON_COLUMNS)
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
