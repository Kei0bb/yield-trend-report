"""Explore-page service: raw-bin aggregation with top-10 + "Other" collapsing."""

import logging

from app.models.schemas import BinBreakdown, LotData
from app.services.lot_service import get_lots

logger = logging.getLogger(__name__)

_TOP_N = 10
_OTHER = "Other"


def build_explore(
    nickname: str,
    process: str,
    months: int = 6,
    process_values: list[str] | None = None,
) -> tuple[list[LotData], list[str]]:
    """Fetch raw-bin lot data and collapse bins beyond the top 10 into "Other".

    Steps:
    1. Call ``get_lots`` with *raw_bins=True* so the full, unmapped DB bin names
       are used as categories.  Anomaly warnings are attached inside ``get_lots``.
    2. Compute each bin's mean percent across **all** lots (lots missing a bin
       contribute 0% for that lot to the mean denominator).
    3. Keep the top 10 bins by mean percent (descending). Every remaining bin is
       collapsed into a single "Other" entry per lot: summed percent/count,
       union of bin_codes.
    4. Return ``(lots, available_bins)`` where ``available_bins`` is the top-10
       names ordered by mean desc, followed by "Other" when something was
       collapsed.

    The returned ``LotData`` objects are modified in-place (bin_breakdown
    rewritten); all other fields (yield_pct, lot_date, wafer_count, warnings)
    are preserved unchanged.

    When *process_values* is given, only those DB PROCESS values are queried
    (sub-process drill-down); otherwise the process's full merged set is used.
    """
    lots = get_lots(nickname, process, months, raw_bins=True, process_values=process_values, split_by_rev=True)
    if not lots:
        return lots, []

    n_lots = len(lots)

    # --- 1. Collect all bin names and their per-lot percent ---
    all_bins: set[str] = set()
    for lot in lots:
        for b in lot.bin_breakdown:
            all_bins.add(b.bin_name)

    # mean percent across all lots (absent lots contribute 0)
    bin_lot_pct: dict[str, dict[str, float]] = {b: {} for b in all_bins}
    for lot in lots:
        for b in lot.bin_breakdown:
            bin_lot_pct[b.bin_name][lot.lot_id] = b.percent

    bin_mean: dict[str, float] = {
        name: sum(pct_by_lot.values()) / n_lots
        for name, pct_by_lot in bin_lot_pct.items()
    }

    # --- 2. Select top-N bins by mean percent (descending) ---
    sorted_bins = sorted(bin_mean.keys(), key=lambda b: bin_mean[b], reverse=True)
    top_bins: list[str] = sorted_bins[:_TOP_N]
    other_bins: set[str] = set(sorted_bins[_TOP_N:])

    logger.debug(
        "build_explore %s/%s: %d total bins → top %d kept, %d collapsed to Other",
        nickname, process, len(all_bins), len(top_bins), len(other_bins),
    )

    # --- 3. Rewrite each lot's bin_breakdown ---
    for lot in lots:
        kept: list[BinBreakdown] = []
        other_count = 0
        other_pct = 0.0
        other_codes: set[int] = set()

        for b in lot.bin_breakdown:
            if b.bin_name in other_bins:
                other_count += b.count
                other_pct += b.percent
                other_codes.update(b.bin_codes)
            else:
                kept.append(b)

        if other_bins and (other_count > 0 or other_pct > 0.0):
            kept.append(BinBreakdown(
                bin_name=_OTHER,
                bin_codes=sorted(other_codes),
                count=other_count,
                percent=round(other_pct, 3),
            ))

        lot.bin_breakdown = kept

    # --- 4. Build available_bins list ---
    available_bins: list[str] = list(top_bins)
    if other_bins:
        available_bins.append(_OTHER)

    return lots, available_bins
