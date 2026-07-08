"""Wafer Map service: per-lot cached die data + legend with resolved labels."""

import logging

import pandas as pd

from app.config import settings
from app.models.schemas import (
    WaferMapLegendItem,
    WaferMapResponse,
    WaferMapWafer,
)
from app.services.map_queries import BIN_META_COLUMNS, DIE_COLUMNS, query_bin_meta, query_die_map
from app.services.mock_data import mock_bin_meta_dataframe, mock_die_dataframe
from app.services.product_config import (
    primary_product_id,
    resolve_display_name,
    resolve_process_filter,
)
from app.services.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_die_cache = TTLCache(maxsize=128)


def _load_die_df(nickname, process, lot_id, process_values):
    if settings.USE_MOCK_DATA:
        mock_process = process_values[0] if process_values else process.upper()
        return mock_die_dataframe(lot_id, mock_process)
    return query_die_map([lot_id], process_values)


def _die_df_cached(nickname, process, lot_id, process_values):
    key = f"mapdf:{nickname}:{process}:{lot_id}:{','.join(process_values or [])}"
    return _die_cache.get_or_compute(
        key, lambda: _load_die_df(nickname, process, lot_id, process_values)
    ).copy()


def _load_bin_meta(nickname, process, lot_id, process_values):
    if settings.USE_MOCK_DATA:
        mock_process = process_values[0] if process_values else process.upper()
        return mock_bin_meta_dataframe(lot_id, mock_process)
    return query_bin_meta([lot_id], process_values)


def _bin_meta_cached(nickname, process, lot_id, process_values):
    key = f"mapmeta:{nickname}:{process}:{lot_id}:{','.join(process_values or [])}"
    return _die_cache.get_or_compute(
        key, lambda: _load_bin_meta(nickname, process, lot_id, process_values)
    ).copy()


def clear_map_cache() -> None:
    _die_cache.clear()


def _is_pass(quality) -> bool:
    return str(quality or "").strip().upper() == "PASS"


def _bin_labels(nickname, process, meta_df, codes):
    """Resolve display labels for bin codes: pure DB BIN_SUM bin_name →
    str(code). Returns {code: label}."""
    labels: dict[int, str] = {}
    if not meta_df.empty and "bin_name" in meta_df.columns:
        names = meta_df.dropna(subset=["bin_name"]).set_index("bin_code")["bin_name"]
        for code in codes:
            name = str(names.get(code, "") or "")
            if name:
                labels[code] = f"{code}_{name}"

    for code in codes:
        labels.setdefault(code, str(code))
    return labels


def get_wafer_maps(
    nickname: str,
    process: str,
    lot_ids: list[str],
    months: int = 6,
    sub: str | None = None,
) -> WaferMapResponse:
    """Build the Wafer Map response for the given lots.

    `months` is unused now that bin labels are resolved from the per-lot
    SEMI_CP_BIN_SUM metadata lookup instead of the lot-DF cache; it is kept
    in the signature for router compatibility.
    """
    process_values = [sub] if sub else (resolve_process_filter(nickname, process) or [process.upper()])

    frames = [_die_df_cached(nickname, process, lot, process_values) for lot in lot_ids]
    frames = [f for f in frames if not f.empty]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DIE_COLUMNS)

    meta_frames = [_bin_meta_cached(nickname, process, lot, process_values) for lot in lot_ids]
    meta_frames = [f for f in meta_frames if not f.empty]
    meta_df = (
        pd.concat(meta_frames, ignore_index=True).drop_duplicates("bin_code")
        if meta_frames else pd.DataFrame(columns=BIN_META_COLUMNS)
    )

    wafers: list[WaferMapWafer] = []
    for (lot_id, wafer_id), g in df.groupby(["lot_id", "wafer_id"], sort=True):
        wafers.append(WaferMapWafer(
            lot_id=str(lot_id),
            wafer_id=str(wafer_id),
            x=[int(v) for v in g["x"]],
            y=[int(v) for v in g["y"]],
            bin=[int(v) for v in g["bin_code"]],
        ))

    pass_codes = (
        sorted({int(c) for c in meta_df.loc[meta_df["bin_quality"].map(_is_pass), "bin_code"]})
        if not meta_df.empty else []
    )

    fail_df = df.loc[~df["bin_code"].isin(pass_codes)] if not df.empty else df
    counts = fail_df.groupby("bin_code").size().sort_values(ascending=False) if not fail_df.empty else pd.Series(dtype=int)
    labels = _bin_labels(nickname, process, meta_df, [int(c) for c in counts.index])
    legend = [
        WaferMapLegendItem(bin_code=int(code), label=labels[int(code)], count=int(n))
        for code, n in counts.items()
    ]

    return WaferMapResponse(
        product_id=primary_product_id(nickname),
        display_name=resolve_display_name(nickname),
        process=sub or process,
        wafers=wafers,
        legend=legend,
        pass_bin_codes=pass_codes,
    )
