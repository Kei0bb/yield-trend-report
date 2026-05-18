import random
from pathlib import Path

import pandas as pd

from app.config import settings
from app.database import get_connection, release_connection
from app.models.schemas import ProcessData

# backend/ 直下の設定ファイル
_BACKEND_ROOT        = Path(__file__).parent.parent.parent
_BIN_MAPPINGS_DIR    = _BACKEND_ROOT / "bin_mappings"          # 製品別 bin マッピングディレクトリ
_BIN_GROUP_CSV       = _BACKEND_ROOT / "bin_group.csv"          # 旧フォーマット (フォールバック用)
_PRODUCT_CONFIG_CSV  = _BACKEND_ROOT / "product_config.csv"

# bin_group 未指定時のデフォルト識別子
_DEFAULT_BIN_GROUP = "default"
# process 未指定のワイルドカード
_ANY_PROCESS = "*"


# ──────────────────────────────────────────────────────────────────────
# Product 設定 (nickname ↔ CP/FT PRODUCT_ID マッピング)
# ──────────────────────────────────────────────────────────────────────

def _load_product_config() -> dict[str, dict[str, str]] | None:
    """
    product_config.csv を読み込み {nickname: {cp_product_id, ft_product_id, bin_group}} を返す。
    ファイルがなければ None (= mock 時はモック、本番時は DB 全件にフォールバック)。

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


def _resolve_product_ids(nickname: str, process: str) -> list[str]:
    """
    nickname と process から DB クエリ用の PRODUCT_ID リストを解決する。
    1 nickname に対し複数の PRODUCT_ID が紐づく場合に対応 (';' 区切り)。
    product_config.csv がない場合は nickname をそのまま 1 件として返す。

    例: cp_product_id="SCT101A;SCT101B" → ["SCT101A", "SCT101B"]
    """
    config = _load_product_config()
    if config is None or nickname not in config:
        return [nickname] if nickname else []
    key = f"{process.lower()}_product_id"
    raw = config[nickname].get(key, "")
    if not raw:
        return []
    # ';' / ',' どちらでも分割
    ids = [pid.strip() for pid in raw.replace(",", ";").split(";")]
    return [pid for pid in ids if pid]


def _resolve_product_id(nickname: str, process: str) -> str:
    """[後方互換] 単一 PRODUCT_ID を返す。複数あれば先頭のみ。"""
    ids = _resolve_product_ids(nickname, process)
    return ids[0] if ids else ""


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


# ──────────────────────────────────────────────────────────────────────
# Bin マッピング (製品ごとに別 CSV ファイル)
#   bin_mappings/<bin_group>.csv を読み込んで {process: {bin_code: bin_group_name}} を返す
# ──────────────────────────────────────────────────────────────────────

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
        2. DB の SEMI_CP_HEADER.PRODUCT_ID 全件 (mock 時はモック品種)
    """
    # product_config.csv は mock / 本番ともに優先 (nickname テストのため)
    config = _load_product_config()
    if config is not None:
        return list(config.keys())

    if settings.USE_MOCK_DATA:
        return _mock_products()

    # フォールバック: DB 全件
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
    各 nickname の PRODUCT_ID を全て集めて IN 句で 1 クエリ実行する。

    対応するケース:
    - 1 nickname に複数 PRODUCT_ID (例: cp_product_id="SCT101A;SCT101B")
    - 複数 nickname (例: 改版品種で同じ display_name を持つ)
    - 上記の組み合わせ
    """
    if not nicknames:
        return ProcessData(lots=[], yield_avg=[], fail_bins={})

    # DataFrame 取得 (mock / 本番 共通フォーマット)
    if settings.USE_MOCK_DATA:
        # mock は display_name をシードに 1 つの DataFrame を生成
        display = resolve_display_name(nicknames[0])
        df = _mock_yield_dataframe(display, start_month, end_month, process)
    else:
        # 全 nickname の PRODUCT_ID を集約・重複排除して IN 句で 1 クエリ
        all_pids: list[str] = []
        for nickname in nicknames:
            for pid in _resolve_product_ids(nickname, process):
                if pid not in all_pids:
                    all_pids.append(pid)
        if not all_pids:
            return ProcessData(lots=[], yield_avg=[], fail_bins={})

        if process == "CP":
            df = _query_cp(all_pids, start_month, end_month, process)
        elif process == "FT":
            df = _query_ft(all_pids, start_month, end_month, process)
        else:
            return ProcessData(lots=[], yield_avg=[], fail_bins={})

    if df.empty:
        return ProcessData(lots=[], yield_avg=[], fail_bins={})

    # bin_group マッピング適用 → 集計 (mock / 本番 共通)
    bin_group = _resolve_bin_group(nicknames[0])
    df = _apply_bin_groups(df, bin_group=bin_group, process=process)
    return _aggregate_lot_data(df)


def _build_in_clause(product_ids: list[str]) -> tuple[str, dict[str, str]]:
    """PRODUCT_ID リストから IN 句と bind 変数辞書を生成。"""
    bind_names = [f"pid{i}" for i in range(len(product_ids))]
    clause = ", ".join(f":{n}" for n in bind_names)
    binds = {bind_names[i]: pid for i, pid in enumerate(product_ids)}
    return clause, binds


def _query_cp(
    product_ids: list[str], start_month: str, end_month: str, process: str
) -> pd.DataFrame:
    """CP: SEMI_CP_BIN_SUM は集計済みなので BIN_COUNT をそのまま使用"""
    in_clause, pid_binds = _build_in_clause(product_ids)
    query = f"""
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
        WHERE h.PRODUCT_ID  IN ({in_clause})
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
            **pid_binds,
            "process": process,
            "start_month": start_month,
            "end_month": end_month,
        },
    )


def _query_ft(
    product_ids: list[str], start_month: str, end_month: str, process: str
) -> pd.DataFrame:
    """
    FT: SEMI_FT_BIN_SUM は CP と同じく集計済みのため BIN_COUNT をそのまま使用。
    CP との違いは：
      - テーブル名が SEMI_FT_HEADER / SEMI_FT_BIN_SUM
      - FT は ASSY_LOT_ID を持つため JOIN キーに含める
    """
    in_clause, pid_binds = _build_in_clause(product_ids)
    query = f"""
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
        WHERE h.PRODUCT_ID  IN ({in_clause})
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
            **pid_binds,
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


def _mock_yield_dataframe(
    product: str, start_month: str, end_month: str, process: str
) -> pd.DataFrame:
    """
    DB クエリと同じ形式の DataFrame をモックで生成。
    後段で _apply_bin_groups() / _aggregate_lot_data() を通すため
    bin_mappings/<group>.csv が mock 環境でも正しく反映される。
    """
    random.seed(hash(f"{product}-{process}-{start_month}") % 2**32)

    num_lots = random.randint(6, 12)
    year = int(start_month[:4])
    start_week = int(start_month[5:7]) * 4
    lots = [f"{year}W{str(start_week + i).zfill(2)}" for i in range(num_lots)]

    base_yield = {"CP": 96.0, "FT": 94.0, "SLT": 92.0}.get(process, 95.0)

    # process 別の bin_code (DB の BIN_CODE と同じ数値)
    bin_codes_map = {
        "CP": [3, 5, 7, 9, 11],
        "FT": [2, 4, 6, 8],
        "SLT": [3, 5, 7, 9, 11],
    }
    # bin_code → 簡易 BIN_NAME (bin_mappings がなければそのまま表示される)
    bin_name_map = {
        2: "DC-Fail", 3: "Open/Short", 4: "Function", 5: "Short",
        6: "Speed", 7: "Leak", 8: "Power", 9: "Functional", 11: "Parametric",
    }
    bin_codes = bin_codes_map.get(process, [3, 5, 7])

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
                "bin_name": bin_name_map.get(bin_code, f"Bin{bin_code}"),
                "bin_fail_count": fail_count,
            })
    return pd.DataFrame(rows, columns=_COMMON_COLUMNS)
