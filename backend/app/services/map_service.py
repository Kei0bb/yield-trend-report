"""Wafer Map service: per-lot cached die data + legend with resolved labels."""

import logging

import pandas as pd

from app.config import settings
from app.models.schemas import (
    WaferMapLegendItem,
    WaferMapResponse,
    WaferMapWafer,
)
from app.services.bin_mapping import load_bin_mapping
from app.services.lot_service import _load_dataframe
from app.services.map_queries import DIE_COLUMNS, query_die_map
from app.services.mock_data import mock_die_dataframe
from app.services.product_config import (
    ANY_PROCESS,
    primary_product_id,
    resolve_bin_group,
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


def clear_map_cache() -> None:
    _die_cache.clear()


def _is_pass(quality) -> bool:
    return str(quality or "").strip().upper() == "PASS"


def _bin_labels(nickname, process, months, process_values, codes):
    """Resolve display labels for bin codes: bin_mappings CSV → lot-DF DB
    names → str(code). Returns {code: label}."""
    labels: dict[int, str] = {}

    mapping = load_bin_mapping(resolve_bin_group(nickname, process))
    per_proc = {**mapping.get(ANY_PROCESS, {}), **mapping.get(process.upper(), {})}
    for code in codes:
        if code in per_proc:
            labels[code] = f"{code}_{per_proc[code]}"

    unresolved = [c for c in codes if c not in labels]
    if unresolved:
        # Reuse the lot-DF cache with the same key the router builds for
        # GET /wafermap/lots ([sub] if sub else None, not the fully-resolved
        # process_values), so this hits that cache entry instead of firing a
        # second, differently-keyed Oracle query.
        lot_df = _load_dataframe(nickname, process, months, process_values=process_values)
        if not lot_df.empty and "raw_bin_code" in lot_df.columns:
            names = (
                lot_df.dropna(subset=["bin_name"])
                .groupby("raw_bin_code")["bin_name"]
                .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "")
            )
            for code in unresolved:
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
    process_values = [sub] if sub else (resolve_process_filter(nickname, process) or [process.upper()])

    frames = [_die_df_cached(nickname, process, lot, process_values) for lot in lot_ids]
    frames = [f for f in frames if not f.empty]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DIE_COLUMNS)

    wafers: list[WaferMapWafer] = []
    for (lot_id, wafer_id), g in df.groupby(["lot_id", "wafer_id"], sort=True):
        wafers.append(WaferMapWafer(
            lot_id=str(lot_id),
            wafer_id=str(wafer_id),
            x=[int(v) for v in g["x"]],
            y=[int(v) for v in g["y"]],
            bin=[int(v) for v in g["bin_code"]],
        ))

    pass_mask = df["bin_quality"].map(_is_pass) if not df.empty else pd.Series(dtype=bool)
    pass_codes = sorted({int(c) for c in df.loc[pass_mask, "bin_code"]}) if not df.empty else []

    fail_df = df.loc[~pass_mask] if not df.empty else df
    counts = fail_df.groupby("bin_code").size().sort_values(ascending=False) if not fail_df.empty else pd.Series(dtype=int)
    # Lot-DF cache lookup uses the router's key convention, not the fully
    # resolved process_values used for the die query/cache above.
    lot_df_process_values = [sub] if sub else None
    labels = _bin_labels(nickname, process, months, lot_df_process_values, [int(c) for c in counts.index])
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
