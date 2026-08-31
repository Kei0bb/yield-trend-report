"""Report のデータが空になる原因を、実 DB に対して段階的に切り分ける診断スクリプト。

SLT (SEMI_FT_*) 用に作ったが、label を変えれば CP / FT でも同じように使える。

    cd backend
    USE_MOCK_DATA=false uv run python scripts/slt_probe.py <product_id> [label] [start] [end]

    例: USE_MOCK_DATA=false uv run python scripts/slt_probe.py SCT101A SLT 2026-03 2026-08

`/api/yield-data`（Report が実際に叩く経路）と同じ順序で 1 段ずつ実行し、各段の件数を出す。
どこで行が消えたかが分かれば、直す場所が SQL なのか設定なのか期間なのかが確定する。

段 5 で 0 行だったときだけ、SQL 側の切り分け（WHERE を 1 条件ずつ足した件数、
実在する PROCESS / REWORK_NEW の値、両テーブルの実際の列）まで自動で降りる。

注意: `/api/debug/probe` は PROCESS 値を `processes:` から解決するため Report とは
経路が違う。このスクリプトは `report:` の `values:` を使う Report と同じ経路を通る。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import get_connection, init_pool, release_connection
from app.services.bin_mapping import apply_bin_groups
from app.services.product_config import (
    nickname_for_product_id,
    resolve_bin_group,
    resolve_process_filter,
    resolve_product_ids,
    resolve_report_unit,
    resolve_report_units,
)
from app.services.yield_aggregator import (
    aggregate_lot_data,
    anchor_from_end_month,
    latest_iso_weeks,
)
# 診断のためにテーブル定義そのものを覗く。アプリ側の唯一の定義元に合わせるため private を参照する。
from app.services.yield_queries import _PROCESS_SPEC, build_yield_query, query_yield_data
from app.services.yield_service import FIXED_WEEK_COUNT

USAGE = "usage: slt_probe.py <product_id|nickname> [label] [start_month] [end_month]"


def head(n: int, title: str) -> None:
    print()
    print("=" * 72)
    print(f"{n}. {title}")
    print("=" * 72)


def run(cur, sql: str, binds: dict | None = None, what: str = ""):
    """1 本流して結果を返す。ORA エラーは 1 行だけ出して None を返す（診断を止めない）。"""
    try:
        cur.execute(sql, binds or {})
        return cur.fetchall()
    except Exception as e:
        print(f"    !! {what or 'query'} でエラー: {str(e).splitlines()[0]}")
        return None


def dump_columns(cur, spec: dict) -> None:
    """両テーブルの実際の列。クエリが前提にしている列が本当に在るかの確認。"""
    wanted = (
        "ASSY_LOT_ID", "SUBSTRATE_ID", "PRODUCT_ID", "PROCESS", "WAFER_ID",
        "EFFECTIVE_NUM", "PASS_CHIP", "MODIFIED_DATE", "REWORK_NEW",
        "BIN_CODE", "BIN_NAME", "BIN_COUNT", "BIN_QUALITY", "DEL_FLAG",
    )
    for tbl in (spec["header"], spec["bin_sum"]):
        rows = run(
            cur,
            "SELECT COLUMN_NAME, DATA_TYPE, NULLABLE FROM ALL_TAB_COLUMNS "
            "WHERE TABLE_NAME = :t ORDER BY COLUMN_ID",
            {"t": tbl},
            f"{tbl} の列一覧",
        )
        if rows is None:
            continue
        if not rows:
            print(f"  {tbl}: ALL_TAB_COLUMNS に無し（シノニム / 別スキーマの可能性）")
            continue
        by_name = {r[0]: r for r in rows}
        print(f"  {tbl}: {len(rows)} 列")
        for want in wanted:
            if want in by_name:
                _, dtype, nullable = by_name[want]
                print(f"    OK   {want:<15} {dtype:<12} NULL可={nullable}")
            else:
                print(f"    ---  {want:<15} 無し")


def bisect_where(cur, spec: dict, pid: str, process_values: list[str],
                 start: str, end: str) -> None:
    """WHERE を 1 条件ずつ足しながらヘッダの件数を数え、どこで 0 になるかを出す。"""
    hdr, date_col = spec["header"], spec["date_col"]
    date_where = (
        f"{date_col} >= TO_DATE(:s || '-01','YYYY-MM-DD') "
        f"AND {date_col} < ADD_MONTHS(TO_DATE(:e || '-01','YYYY-MM-DD'), 1)"
    )
    steps = [
        ("全件（フィルタ無し）", f"SELECT COUNT(*) FROM {hdr}", {}),
        (f"PRODUCT_ID = {pid}",
         f"SELECT COUNT(*) FROM {hdr} WHERE PRODUCT_ID = :p", {"p": pid}),
        (f"  + 期間 {start}..{end}",
         f"SELECT COUNT(*) FROM {hdr} WHERE PRODUCT_ID = :p AND {date_where}",
         {"p": pid, "s": start, "e": end}),
    ]
    if process_values:
        plist = ", ".join(f":v{i}" for i in range(len(process_values)))
        pbinds = {f"v{i}": v for i, v in enumerate(process_values)}
        steps += [
            (f"  + PROCESS IN {process_values}",
             f"SELECT COUNT(*) FROM {hdr} WHERE PRODUCT_ID = :p AND {date_where} "
             f"AND PROCESS IN ({plist})",
             {"p": pid, "s": start, "e": end, **pbinds}),
            ("  + REWORK_NEW = 0",
             f"SELECT COUNT(*) FROM {hdr} WHERE PRODUCT_ID = :p AND {date_where} "
             f"AND PROCESS IN ({plist}) AND REWORK_NEW = 0",
             {"p": pid, "s": start, "e": end, **pbinds}),
        ]
    for what, sql, binds in steps:
        rows = run(cur, sql, binds, what)
        if rows is not None:
            n = rows[0][0]
            print(f"  {n:>10,}  {what}" + ("   <-- ここで 0 件" if n == 0 else ""))


def dump_actual_values(cur, spec: dict, pid: str) -> None:
    """その PRODUCT_ID に実在する PROCESS / REWORK_NEW の値。設定値との食い違いを見る。"""
    hdr, date_col = spec["header"], spec["date_col"]
    rows = run(
        cur,
        f"SELECT PROCESS, COUNT(*), MIN({date_col}), MAX({date_col}) FROM {hdr} "
        f"WHERE PRODUCT_ID = :p GROUP BY PROCESS ORDER BY 2 DESC",
        {"p": pid}, "PROCESS 一覧",
    )
    if rows is not None:
        if not rows:
            print(f"  PRODUCT_ID={pid} の行が {hdr} に 1 件も無い")
            like = run(
                cur,
                f"SELECT DISTINCT PRODUCT_ID FROM {hdr} "
                "WHERE PRODUCT_ID LIKE :p AND ROWNUM <= 20",
                {"p": f"%{pid[:4]}%"}, "PRODUCT_ID 類似検索",
            )
            print(f"  '{pid[:4]}' を含む PRODUCT_ID: {[r[0] for r in (like or [])]}")
        for r in rows:
            print(f"  PROCESS={r[0]!r:<14} {r[1]:>9,} 行   {r[2]} .. {r[3]}")

    rows = run(
        cur,
        f"SELECT REWORK_NEW, COUNT(*) FROM {hdr} WHERE PRODUCT_ID = :p "
        "GROUP BY REWORK_NEW ORDER BY 2 DESC",
        {"p": pid}, "REWORK_NEW 一覧",
    )
    if rows is not None:
        for r in rows:
            note = "   <-- NULL は `= 0` で全部落ちる" if r[0] is None else ""
            print(f"  REWORK_NEW={str(r[0]):<6} {r[1]:>9,} 行{note}")


def main() -> int:
    if len(sys.argv) < 2:
        print(USAGE)
        return 2
    key = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else "SLT"
    start = sys.argv[3] if len(sys.argv) > 3 else "2026-03"
    end = sys.argv[4] if len(sys.argv) > 4 else "2026-08"

    print(f"USE_MOCK_DATA = {settings.USE_MOCK_DATA}")
    if settings.USE_MOCK_DATA:
        print("  !! モックモード。DB は引かれない。USE_MOCK_DATA=false を付けて再実行。")
        return 1
    init_pool()

    head(1, "product_id -> nickname")
    nick = nickname_for_product_id(key) or key
    print(f"  入力          : {key}")
    print(f"  nickname      : {nick}")

    head(2, "report unit の解決（Report が送るラベル -> family / values）")
    print(f"  この製品の unit: {resolve_report_units(nick)}")
    unit = resolve_report_unit(nick, label)
    print(f"  label={label!r} -> {unit}")
    if unit is None:
        print(f"  !! label={label!r} が report: に無い。family={label.upper()!r} / values=None で続行")
    family = unit["family"] if unit else label.upper()
    values = unit["values"] if unit else None
    print(f"  family        : {family}   <- どのテーブルを引くかを決める")
    spec = _PROCESS_SPEC.get(family.upper())
    if spec is None:
        print(f"  !! family={family!r} に対応するテーブル定義が無い。ここで空データが返る。")
        return 1
    print(f"  引くテーブル  : {spec['header']} / {spec['bin_sum']} ({spec['join_type']})")

    head(3, "PRODUCT_ID の解決")
    pids = resolve_product_ids(nick, family)
    print(f"  PRODUCT_ID    : {pids}")
    if not pids:
        print("  !! 空。DB を引かずに空データが返る（yield_service の early return）")
        return 1

    head(4, "PROCESS 値の最終決定")
    if values is None:
        values = resolve_process_filter(nick, family)
        print(f"  report unit が無いので resolve_process_filter -> {values}")
        if values is None:
            print(f"  !! None。SQL は h.PROCESS IN ('{family}') というリテラルで引く")
    final_values = values or [family]
    print(f"  最終 PROCESS  : {final_values}")

    head(5, "SQL 実行")
    sql, _ = build_yield_query(family, pids, values)
    print(sql)
    df = query_yield_data(family, pids, start, end, process_values=values)
    print(f"  取得行数      : {len(df):,}")

    if df.empty:
        print("  !! 0 行。SQL 層で消えている。以下で WHERE を切り分ける。")
        conn = get_connection()
        cur = conn.cursor()
        try:
            head(6, "WHERE を 1 条件ずつ足したときの件数")
            bisect_where(cur, spec, pids[0], final_values, start, end)
            head(7, "その PRODUCT_ID に実在する値")
            dump_actual_values(cur, spec, pids[0])
            head(8, f"{spec['header']} / {spec['bin_sum']} の実際の列")
            dump_columns(cur, spec)
        finally:
            cur.close()
            release_connection(conn)
        return 1

    print(df.head(5).to_string())
    weeks = sorted(df["lot_id"].dropna().unique())
    print(f"  データ内の週  : {weeks[0]} .. {weeks[-1]}  ({len(weeks)} 週)")
    print(f"  bin が null   : {df['raw_bin_code'].isna().sum():,} / {len(df):,} 行（外部結合で bin 無し）")

    head(6, "チャートに載る 12 週ウィンドウ")
    anchor = anchor_from_end_month(end)
    target = latest_iso_weeks(anchor, FIXED_WEEK_COUNT)
    print(f"  end_month={end} -> anchor={anchor}（今日で頭打ち）")
    print(f"  target_lots   : {target}")
    overlap = [w for w in weeks if w in target]
    print(f"  重なり        : {overlap or 'なし'}")
    if not overlap:
        print("  !! ここが原因。SQL は行を返しているが全部ウィンドウの外なので、")
        print("     yield_avg が全部 None になり『データなし』に見える。")
        print("     直すのは SQL ではなく end_month（または FIXED_WEEK_COUNT）。")

    head(7, "bin グループ適用")
    bg = resolve_bin_group(nick, family)
    print(f"  bin_group     : {bg}")
    mapped = apply_bin_groups(df, bin_group=bg, process=family)
    print(f"  bin_code      : {sorted(mapped['bin_code'].dropna().unique())[:15]}")
    print(f"  null bin_code : {mapped['bin_code'].isna().sum():,} 行")

    head(8, "集計結果（API が返すもの）")
    out = aggregate_lot_data(mapped, target_lots=target)
    print(f"  lots          : {out.lots}")
    print(f"  yield_avg     : {out.yield_avg}")
    print(f"  fail_bins     : {list(out.fail_bins)[:10]}")
    if all(v is None for v in out.yield_avg):
        print("  !! yield_avg が全 None -> フロントは空チャートを描く")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
