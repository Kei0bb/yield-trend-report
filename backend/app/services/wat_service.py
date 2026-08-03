"""PCM/WAT service: per-lot item statistics, judgement, and scatter pairing.

Everything here is scoped to a single lot — there is no cross-lot
aggregation. Statistics run on the raw site-level measurements, which is the
usual definition of Cpk in a fab.
"""

import logging
import math
from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.models.schemas import (
    WatItemStats, WatLotInfo, WatLotsResponse, WatSummaryResponse,
)
from app.services.mock_data import mock_wat_dataframe, mock_wat_lots
from app.services.product_config import (
    primary_product_id, resolve_display_name, resolve_wat_pairs,
)
from app.services.wat_queries import (
    WAT_DETAIL_COLUMNS, query_wat_detail, query_wat_lots,
)

logger = logging.getLogger(__name__)

# Process-capability thresholds. Comparisons are strictly "less than", so a
# Cpk of exactly 1.00 is yellow (not red) and exactly 1.33 is ok (not yellow).
CPK_RED = 1.00
CPK_YELLOW = 1.33


def _clean(value) -> float | None:
    """NaN and pandas NA collapse to None — NaN is not valid JSON."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def resolve_spec(series: pd.Series, item_name: str) -> float | None:
    """The spec limit for an item, assumed constant within a lot.

    When several distinct values appear, the most common one wins (ties break
    on ascending sort) and a WARNING is logged — silently picking one would
    hide a real data problem.
    """
    values = series.dropna()
    if values.empty:
        return None
    counts = values.value_counts()
    if len(counts) > 1:
        logger.warning(
            "WAT item %s has %d distinct spec values in one lot: %s — using the most common",
            item_name, len(counts), sorted(counts.index.tolist()),
        )
    top = counts.max()
    winners = sorted(v for v, c in counts.items() if c == top)
    return _clean(winners[0])


def count_out_of_spec(values: pd.Series, spec_low, spec_high) -> int:
    """Measurements strictly outside the limits. A value exactly on a limit is
    in spec."""
    clean = values.dropna()
    if clean.empty:
        return 0
    mask = pd.Series(False, index=clean.index)
    if spec_low is not None:
        mask |= clean < spec_low
    if spec_high is not None:
        mask |= clean > spec_high
    return int(mask.sum())


def compute_cpk(mean, sigma, spec_low, spec_high, n: int, oos_count: int
                ) -> tuple[float | None, str]:
    """Returns (cpk, cpk_state) where state is value / infinite / undefined.

    JSON cannot carry Infinity, so a zero-sigma in-spec item reports
    cpk=None with state="infinite" and the UI prints the symbol.
    """
    if spec_low is None and spec_high is None:
        return None, "undefined"
    if n < 2:
        return None, "undefined"
    s = _clean(sigma)
    m = _clean(mean)
    if s is None or m is None:
        return None, "undefined"
    if s == 0:
        # Every measurement identical: infinitely capable if it sits in spec,
        # meaningless if it does not.
        return (None, "undefined") if oos_count > 0 else (None, "infinite")

    candidates = []
    if spec_high is not None:
        candidates.append((spec_high - m) / (3 * s))
    if spec_low is not None:
        candidates.append((m - spec_low) / (3 * s))
    return min(candidates), "value"


def classify_status(cpk, cpk_state: str, oos_count: int) -> str:
    """Evaluated top-down; the first match wins.

    The order matters: an item with n<2 (undefined Cpk) that also has a
    failing measurement must read red, not gray.
    """
    if oos_count > 0 or (cpk_state == "value" and cpk < CPK_RED):
        return "red"
    if cpk_state == "value" and cpk < CPK_YELLOW:
        return "yellow"
    if cpk_state == "undefined":
        return "gray"
    return "ok"


def _wafer_series(group: pd.DataFrame) -> list[dict]:
    """Per-wafer mean and sigma, wafer number ascending.

    A wafer measured at a single site has no sample sigma; its error bar is
    omitted rather than drawn as zero.
    """
    out: list[dict] = []
    for wafer_id, g in group.groupby("wafer_id", sort=True):
        values = g["meas_data"].dropna()
        n = int(len(values))
        out.append({
            "wafer_id": int(wafer_id),
            "n": n,
            "mean": _clean(values.mean()) if n else None,
            "sigma": _clean(values.std(ddof=1)) if n >= 2 else None,
        })
    return out


def compute_item_stats(group: pd.DataFrame, item_name: str) -> dict:
    """Statistics for one ITEM_NAME across every wafer and site of one lot."""
    spec_low = resolve_spec(group["spec_low"], item_name)
    spec_high = resolve_spec(group["spec_high"], item_name)

    units = group["item_unit"].dropna()
    unit = str(units.iloc[0]) if not units.empty else ""

    values = group["meas_data"].dropna()
    n = int(len(values))
    oos_count = count_out_of_spec(group["meas_data"], spec_low, spec_high)

    mean = _clean(values.mean()) if n else None
    sigma = _clean(values.std(ddof=1)) if n >= 2 else None
    cpk, cpk_state = compute_cpk(mean, sigma, spec_low, spec_high, n, oos_count)

    return {
        "item_name": item_name,
        "unit": unit,
        "spec_low": spec_low,
        "spec_high": spec_high,
        "n": n,
        "mean": mean,
        "sigma": sigma,
        "min": _clean(values.min()) if n else None,
        "max": _clean(values.max()) if n else None,
        "cpk": _clean(cpk),
        "cpk_state": cpk_state,
        "oos_count": oos_count,
        "oos_pct": round(oos_count / n * 100, 4) if n else 0.0,
        "status": classify_status(cpk, cpk_state, oos_count),
        "wafer_series": _wafer_series(group),
    }


# (kind, pair key for x, pair key for y) — the response always carries these
# four plots in this order so the UI can lay them out without sorting.
SCATTER_KINDS: list[tuple[str, str, str]] = [
    ("vth_np", "vth_n", "vth_p"),
    ("idsat_np", "idsat_n", "idsat_p"),
    ("ion_vt_n", "vth_n", "idsat_n"),
    ("ion_vt_p", "vth_p", "idsat_p"),
]


def _site_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Wide view indexed by (wafer_id, site_no) with one column per item.

    Pairing happens on this index: a point exists only where both items were
    measured at the same wafer and the same site.
    """
    if df.empty:
        return pd.DataFrame()
    return df.pivot_table(
        index=["wafer_id", "site_no"],
        columns="item_name",
        values="meas_data",
        aggfunc="mean",
    )


def _plot_points(matrix: pd.DataFrame, x_item: str, y_item: str) -> list[dict]:
    if matrix.empty or x_item not in matrix.columns or y_item not in matrix.columns:
        return []
    sub = matrix[[x_item, y_item]].dropna()
    return [
        {
            "wafer_id": int(wafer_id),
            "site_no": int(site_no),
            "x": float(row[x_item]),
            "y": float(row[y_item]),
        }
        for (wafer_id, site_no), row in sub.iterrows()
    ]


def build_scatter_pairs(df: pd.DataFrame, pairs: list[dict],
                        stats_by_item: dict[str, dict]) -> list[dict]:
    """Scatter data for every configured device flavor.

    A configured item that is absent from the data yields an empty plot rather
    than an error — the other three plots of that flavor still render.
    """
    if not pairs:
        return []

    matrix = _site_matrix(df)

    def spec_of(item: str) -> list:
        st = stats_by_item.get(item) or {}
        return [st.get("spec_low"), st.get("spec_high")]

    def unit_of(item: str) -> str:
        return (stats_by_item.get(item) or {}).get("unit", "")

    out: list[dict] = []
    for pair in pairs:
        plots = []
        for kind, x_key, y_key in SCATTER_KINDS:
            x_item = pair.get(x_key, "")
            y_item = pair.get(y_key, "")
            plots.append({
                "kind": kind,
                "x_item": x_item,
                "y_item": y_item,
                "x_unit": unit_of(x_item),
                "y_unit": unit_of(y_item),
                "x_spec": spec_of(x_item),
                "y_spec": spec_of(y_item),
                "points": _plot_points(matrix, x_item, y_item),
            })
        out.append({"label": pair.get("label", ""), "plots": plots})
    return out


# ---------------------------------------------------------------------------
# Data loading (mock / real DB)
# ---------------------------------------------------------------------------

def _load_lots(product_id: str, months: int) -> pd.DataFrame:
    if settings.USE_MOCK_DATA:
        return mock_wat_lots(product_id, months)
    today = date.today()
    start = today - timedelta(days=months * 30)
    end = today + timedelta(days=1)   # exclusive upper bound keeps today's data
    return query_wat_lots(product_id, start, end)


def _load_detail(product_id: str, lot_id: str) -> pd.DataFrame:
    if settings.USE_MOCK_DATA:
        return mock_wat_dataframe(product_id, lot_id)
    return query_wat_detail(product_id, lot_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_wat_lots(nickname: str, product_id: str, months: int) -> WatLotsResponse:
    """WAT lots for a product, newest first."""
    df = _load_lots(product_id, months)
    lots: list[WatLotInfo] = []
    if not df.empty:
        ordered = df.sort_values("last_measured", ascending=False)
        lots = [
            WatLotInfo(
                lot_id=str(r.lot_id),
                last_measured=str(r.last_measured)[:10],
                wafer_count=int(r.wafer_count),
            )
            for r in ordered.itertuples()
        ]
    return WatLotsResponse(product_id=product_id, lots=lots)


def get_wat_summary(nickname: str, product_id: str, lot_id: str) -> WatSummaryResponse:
    """Item statistics and scatter series for one lot."""
    df = _load_detail(product_id, lot_id)
    if df.empty:
        df = pd.DataFrame(columns=WAT_DETAIL_COLUMNS)

    stats: list[dict] = []
    for item_name, group in df.groupby("item_name", sort=True):
        stats.append(compute_item_stats(group, str(item_name)))

    stats_by_item = {s["item_name"]: s for s in stats}
    scatter_pairs = (
        []
        if df.empty
        else build_scatter_pairs(df, resolve_wat_pairs(nickname), stats_by_item)
    )

    measured_date = ""
    wafer_count = 0
    if not df.empty:
        wafer_count = int(df["wafer_id"].nunique())
        stamps = df["start_time"].dropna()
        if not stamps.empty:
            measured_date = str(stamps.max())[:10]

    return WatSummaryResponse(
        product_id=primary_product_id(nickname) or product_id,
        display_name=resolve_display_name(nickname),
        lot_id=lot_id,
        measured_date=measured_date,
        wafer_count=wafer_count,
        items=[WatItemStats(**s) for s in stats],
        scatter_pairs=scatter_pairs,
    )
