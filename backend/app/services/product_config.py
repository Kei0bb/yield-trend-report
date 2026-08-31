import json
import logging
from functools import lru_cache

import yaml

from app.utils.csv_loader import PRODUCT_CONFIG_YAML

logger = logging.getLogger(__name__)

# Sentinel used in bin_mapping resolution for "any process"
ANY_PROCESS = "*"
DEFAULT_BIN_GROUP = "default"


# Processes that share FT's bin-group fallback chain (slt → ft → bin_group).
_FT_FAMILY = {"SLT"}


def _parse_process_entry(entry):
    """Return (major: str|None, subs: list[str]).

    None major means the major row is suppressed (subs-only config).

    Accepted forms:
      scalar  ft: cFT1            → major='cFT1', subs=[]
      list    cp: [CP, CP1, CP2]  → major='CP' (first), subs=['CP1','CP2']
      list-1  ft: [cFT1]          → major='cFT1', subs=[]
      dict    cp: {major: CP, subs: [CP1, CP2]}
      subs-only cp: {subs: [CP1, CP2]} → major=None, subs=['CP1','CP2']
      major-only cp: {major: CP}       → major='CP', subs=[]
    """
    if entry is None:
        return None, []
    if isinstance(entry, dict):
        major_raw = entry.get("major")
        major = str(major_raw).strip() if major_raw not in (None, "") else None
        subs_raw = entry.get("subs") or []
        if isinstance(subs_raw, str):
            subs_raw = [subs_raw]
        subs = [str(s).strip() for s in subs_raw if str(s).strip()]
        return major, subs
    if isinstance(entry, (list, tuple)):
        vals = [str(v).strip() for v in entry if str(v).strip()]
        if not vals:
            return None, []
        return vals[0], vals[1:]
    # scalar
    s = str(entry).strip()
    return (s or None), []


def _parse_report_units(raw, nickname: str) -> list[dict]:
    """Parse a product's `report:` list into validated unit dicts.

    Each entry needs non-empty family/label and a non-empty values list
    (a scalar string is accepted and wrapped into a single-element list).
    Malformed entries are skipped with a logged warning.
    """
    if not raw:
        return []
    if not isinstance(raw, (list, tuple)):
        logger.warning("product_config.yaml: %s.report is not a list — ignoring", nickname)
        return []

    units: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            logger.warning("product_config.yaml: %s.report entry %r is not a mapping — skipping", nickname, entry)
            continue
        family_raw = entry.get("family")
        label_raw = entry.get("label")
        values_raw = entry.get("values")

        family = str(family_raw).strip().upper() if family_raw not in (None, "") else ""
        label = str(label_raw).strip() if label_raw not in (None, "") else ""
        if isinstance(values_raw, str):
            values_raw = [values_raw]
        values = [str(v).strip() for v in (values_raw or []) if str(v).strip()]

        if not family or not label or not values:
            logger.warning(
                "product_config.yaml: %s.report entry %r missing family/label/values — skipping",
                nickname, entry,
            )
            continue
        units.append({"family": family, "label": label, "values": values})
    return units


def _parse_target(raw, nickname: str) -> dict[str, float]:
    """Parse a product's `target:` mapping {process_label: percent}.

    Scalars / non-mappings are ignored with a warning (per-process only).
    """
    if raw in (None, ""):
        return {}
    if isinstance(raw, dict):
        out: dict[str, float] = {}
        for k, v in raw.items():
            key = str(k).strip()
            if not key:
                continue
            try:
                out[key] = float(v)
            except (ValueError, TypeError):
                logger.warning("product_config.yaml: %s.target[%r]=%r is not numeric — skipping", nickname, k, v)
        return out
    logger.warning("product_config.yaml: %s.target must be a mapping {label: value}, not a scalar — ignoring", nickname)
    return {}


def _parse_wat_pairs(raw, nickname: str) -> list[dict]:
    """Parse the `wat:` block into a flat list of device-flavor pairs.

    Shape:
        wat:
          pairs:
            - label: Core RVT
              vth:   {n: VTHN_RVT, p: VTHP_RVT}
              idsat: {n: IDSATN_RVT, p: IDSATP_RVT}

    Returns [] when the block is absent or unusable — the scatter section is
    simply omitted for that product rather than erroring.
    """
    if not isinstance(raw, dict):
        return []
    pairs = raw.get("pairs")
    if not isinstance(pairs, list):
        return []

    out: list[dict] = []
    for i, entry in enumerate(pairs):
        label = f"pair{i + 1}"
        if not isinstance(entry, dict):
            logger.warning(
                "product_config[%s].wat.pairs[%d] is not a mapping; skipped", nickname, i
            )
            continue
        label = str(entry.get("label") or label).strip() or label
        vth = entry.get("vth") if isinstance(entry.get("vth"), dict) else {}
        idsat = entry.get("idsat") if isinstance(entry.get("idsat"), dict) else {}
        pair = {
            "label": label,
            "vth_n": str(vth.get("n") or "").strip(),
            "vth_p": str(vth.get("p") or "").strip(),
            "idsat_n": str(idsat.get("n") or "").strip(),
            "idsat_p": str(idsat.get("p") or "").strip(),
        }
        missing = [k for k in ("vth_n", "vth_p", "idsat_n", "idsat_p") if not pair[k]]
        if missing:
            logger.warning(
                "product_config[%s].wat.pairs[%s] missing %s; skipped",
                nickname, label, ", ".join(missing),
            )
            continue
        out.append(pair)
    return out


def _config_from_yaml() -> dict[str, dict[str, str]] | None:
    """Parse product_config.yaml into the flat internal shape.

    Schema (per product, all fields except product_id optional):
        products:
          <nickname>:
            display_name: ...
            product_id: ...            # single id; '%' LIKE wildcard allowed
            bin_group: ...
            bin_groups: {ft: ..., slt: ...}   # optional per-process overrides
            processes:                 # DB PROCESS values per logical process
              cp: CP                  # scalar → single major row
              ft: [cFT1, cFT2]        # list → first=major, rest=sub rows
              slt: {major: cSLT1}     # dict with optional 'subs' key
              # subs-only: cp: {subs: [CP1, CP2]} → no major row, sub rows only

    Per process (cp/ft/slt), three internal keys are stored:
      <p>_set   : "1" when the key was present in the YAML processes mapping
      <p>_major : the DB PROCESS value for the major row, or "" when suppressed
      <p>_subs  : ";"-joined sub-process DB PROCESS values

    `report:` key (REQUIRED for a product to appear on the Report page) defines
    the Report/PDF output units for the product, each with a family (cp/ft/slt),
    a display label, and the DB PROCESS values to query (merged into one series
    when >1):
        report:
          - {family: cp, label: "CP",  values: [CP]}
          - {family: cp, label: "CP1", values: [CP1]}
    Stored as JSON under the "report" key; see resolve_report_units(). A
    configured product with no `report:` (or an empty/invalid one) is simply
    excluded from the Report page — there is no implicit CP/FT/SLT fallback
    once product_config.yaml exists. (The CP/FT/SLT fallback only applies when
    the yaml file itself is absent or the nickname is unconfigured.)

    A bare top-level mapping (no `products:` key) is also accepted.
    """
    with PRODUCT_CONFIG_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    products = data.get("products", data) if isinstance(data, dict) else {}

    config: dict[str, dict[str, str]] = {}
    for nickname, entry in (products or {}).items():
        if not isinstance(entry, dict):
            continue
        name = str(nickname).strip()
        processes = entry.get("processes") or {}
        bin_groups = entry.get("bin_groups") or {}
        product_ids = entry.get("product_ids") or {}

        row: dict[str, str] = {
            "display_name": str(entry.get("display_name") or name).strip() or name,
            "product_id": str(entry.get("product_id") or "").strip(),
            "bin_group": str(entry.get("bin_group") or "").strip() or DEFAULT_BIN_GROUP,
            "ft_bin_group": str(bin_groups.get("ft") or "").strip(),
            "slt_bin_group": str(bin_groups.get("slt") or "").strip(),
            "target": json.dumps(_parse_target(entry.get("target"), name)),
        }

        # Per-process PRODUCT_ID overrides. SLT reads a different schema whose
        # PRODUCT_ID carries a package suffix (SC0G29B -> SC0G29BP3-ES), so it
        # cannot share CP's id. A list is joined with ';' — the same separator
        # resolve_product_ids already splits on.
        for proc in ("cp", "ft", "slt"):
            raw_pid = product_ids.get(proc) if isinstance(product_ids, dict) else None
            if isinstance(raw_pid, (list, tuple)):
                value = ";".join(str(v).strip() for v in raw_pid if str(v).strip())
            else:
                value = str(raw_pid or "").strip()
            row[f"{proc}_product_id"] = value

        for proc in ("cp", "ft", "slt"):
            if isinstance(processes, dict) and proc in processes:
                major, subs = _parse_process_entry(processes[proc])
                row[f"{proc}_set"] = "1"
                row[f"{proc}_major"] = major or ""
                row[f"{proc}_subs"] = ";".join(subs)
            else:
                row[f"{proc}_set"] = ""
                row[f"{proc}_major"] = ""
                row[f"{proc}_subs"] = ""

        report_units = _parse_report_units(entry.get("report"), name)
        row["report"] = json.dumps(report_units)
        row["wat"] = json.dumps(_parse_wat_pairs(entry.get("wat"), name))

        config[name] = row
    return config or None


@lru_cache(maxsize=None)
def load_product_config() -> dict[str, dict[str, str]] | None:
    """Load product configuration as {nickname: {display_name, product_id, bin_group, ...}}.

    FT/SLT data lives in the CP schema under the *same* PRODUCT_ID as CP,
    distinguished only by the PROCESS column (e.g. 'cFT1'), so a product has a
    single `product_id`; per-process PROCESS values come from cp/ft/slt_major
    and cp/ft/slt_subs.

    Returns None when product_config.yaml is absent (falls back to DB enumeration
    or mock). Cached for the process lifetime — restart the server after edits.
    """
    if not PRODUCT_CONFIG_YAML.exists():
        return None
    config = _config_from_yaml()
    if config:
        logger.info("Loaded product_config.yaml: %d products", len(config))
    return config


def resolve_product_ids(nickname: str, process: str = "") -> list[str]:
    """Resolve a nickname to its DB PRODUCT_ID(s) for a process.

    Lookup order:
    1. product_ids.<process>  — a per-process override, for a process whose
       schema uses a different PRODUCT_ID (SLT carries a package suffix)
    2. product_id             — the shared id every other process uses

    There is no cross-process fallback: SLT and FT read different tables, so
    inheriting FT's id would be wrong rather than merely unhelpful.

    Supports ';'-delimited lists and '%' wildcards (a wildcard absorbs new
    package numbers without a config edit). Returns [nickname] as-is when
    product_config.yaml is absent.
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return [nickname] if nickname else []

    entry = config[nickname]
    raw = (entry.get(f"{process.lower()}_product_id", "") if process else "") \
        or entry.get("product_id", "")
    if not raw:
        return []
    ids = [pid.strip() for pid in raw.replace(",", ";").split(";")]
    return [pid for pid in ids if pid]


def resolve_display_name(nickname: str) -> str:
    """Return the display_name for a nickname, or the nickname itself if not configured."""
    config = load_product_config()
    if config is None or nickname not in config:
        return nickname
    return config[nickname].get("display_name", nickname)


def resolve_major_process(nickname: str, process: str) -> str | None:
    """The DB PROCESS value the major row queries, or None to suppress the major row.

    Unconfigured process key → the literal process name (preserves default behavior).
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return process.upper()
    entry = config[nickname]
    if entry.get(f"{process.lower()}_set") != "1":
        return process.upper()          # key absent → default literal
    major = entry.get(f"{process.lower()}_major", "")
    return major or None                # present but empty → suppress major row


def resolve_sub_processes(nickname: str, process: str) -> list[str]:
    """Sub-process DB PROCESS values shown as indented sub rows ([] when none)."""
    config = load_product_config()
    if config is None or nickname not in config:
        return []
    raw = config[nickname].get(f"{process.lower()}_subs", "")
    return [v for v in (x.strip() for x in raw.split(";")) if v]


def resolve_process_filter(nickname: str, process: str) -> list[str] | None:
    """DB PROCESS values for the merged/major view (Report + Explore-no-sub + dashboard).

    Returns [major] when a major is set, else the subs list, else None
    (caller then queries using the literal process name).

    Used by yield_service.py (Report/PDF) and lot_service.py (Explore fallback).
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return None
    if config[nickname].get(f"{process.lower()}_set") != "1":
        return None
    major = config[nickname].get(f"{process.lower()}_major", "")
    if major:
        return [major]
    subs = resolve_sub_processes(nickname, process)
    return subs or None


def resolve_report_units(nickname: str) -> list[dict]:
    """Ordered Report/PDF output units for a product:
    [{"family": "CP", "label": "CP1", "values": ["CP1"]}, ...].

    `values` may be None in the fallback, meaning "resolve via resolve_process_filter".

    A product appears in the Report ONLY if it has a non-empty, valid `report:`
    list — there is no implicit CP/FT/SLT fallback per-product anymore. The
    CP/FT/SLT fallback is used ONLY when product_config.yaml is absent entirely
    (config is None) or the nickname is unconfigured, preserving mock/legacy
    behavior in those cases.
    """
    config = load_product_config()
    fallback = [{"family": f, "label": f, "values": None} for f in ("CP", "FT", "SLT")]
    if config is None or nickname not in config:
        return fallback          # no config file / unknown nickname -> mock/legacy behavior
    raw = config[nickname].get("report", "")
    try:
        units = json.loads(raw) if raw else []
    except Exception:
        units = []
    return units                 # explicit: may be [] meaning "hidden from Report"


def is_report_enabled(nickname: str) -> bool:
    """True when the product has at least one valid Report unit."""
    return bool(resolve_report_units(nickname))


def resolve_report_unit(nickname: str, label: str) -> dict | None:
    """Look up a single report unit by its label, or None."""
    for u in resolve_report_units(nickname):
        if u.get("label") == label:
            return u
    return None


def resolve_wat_pairs(nickname: str) -> list[dict]:
    """Device-flavor pairs for the PCM/WAT scatter plots, in declaration order."""
    config = load_product_config() or {}
    raw = (config.get(nickname) or {}).get("wat") or "[]"
    try:
        pairs = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("product_config[%s].wat is not valid JSON; ignored", nickname)
        return []
    return pairs if isinstance(pairs, list) else []


def resolve_bin_group(nickname: str, process: str = "") -> str:
    """Return the bin_group identifier for a nickname, optionally process-specific.

    Lookup order:
    1. <process>_bin_group  (e.g. ft_bin_group, slt_bin_group) — if set
    2. bin_group            — shared fallback
    SLT falls back to ft_bin_group before bin_group.
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return DEFAULT_BIN_GROUP
    entry = config[nickname]
    if process:
        proc_key = f"{process.lower()}_bin_group"
        specific = entry.get(proc_key, "")
        if not specific and process.upper() in _FT_FAMILY:
            specific = entry.get("ft_bin_group", "")
        if specific:
            return specific
    return entry.get("bin_group", "") or DEFAULT_BIN_GROUP


def resolve_target(nickname: str, label: str | None = None) -> float | None:
    """Per-process yield target (%) for the Dashboard/Explore reference line.

    `label` is the process label: "CP"/"FT"/"SLT" for majors, or the DB
    PROCESS value for sub-processes. Returns None when unset.
    """
    config = load_product_config()
    if config is None or nickname not in config or label is None:
        return None
    raw = config[nickname].get("target", "")
    try:
        mapping = json.loads(raw) if raw else {}
    except Exception:
        return None
    if not isinstance(mapping, dict):
        return None
    val = mapping.get(label)
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def group_by_display_name(nicknames: list[str]) -> dict[str, list[str]]:
    """Group nicknames by their resolved display_name (insertion-order preserved)."""
    groups: dict[str, list[str]] = {}
    for nickname in nicknames:
        display = resolve_display_name(nickname)
        groups.setdefault(display, []).append(nickname)
    return groups


def primary_product_id(nickname: str) -> str:
    """The product's public product_id (process-independent). Falls back to the
    nickname itself when unconfigured."""
    config = load_product_config()
    if config is None or nickname not in config:
        return nickname
    return config[nickname].get("product_id", "") or nickname


def _reverse_product_id_map() -> dict[str, str]:
    """Map every configured product_id back to its nickname."""
    config = load_product_config()
    rev: dict[str, str] = {}
    if not config:
        return rev
    for nickname, entry in config.items():
        pid = entry.get("product_id", "")
        if pid:
            rev.setdefault(pid, nickname)
    return rev


def nickname_for_product_id(product_id: str) -> str | None:
    """Reverse-resolve a product_id to its nickname, or None if not found."""
    return _reverse_product_id_map().get(product_id)


def to_nicknames(product_ids: list[str]) -> list[str]:
    """Map UI-facing product_ids to internal nicknames.

    Falls back to the value as-is when it is not a known product_id (so plain
    nicknames and mock/unconfigured ids still resolve). Order preserved.
    """
    return [nickname_for_product_id(pid) or pid for pid in product_ids]


def list_products() -> list[dict[str, str]]:
    """Public product list for the UI: one entry per configured nickname,
    exposing the product_id + display_name (no nickname leaked)."""
    config = load_product_config()
    if not config:
        return []
    return [
        {"product_id": primary_product_id(nick), "display_name": entry.get("display_name", nick)}
        for nick, entry in config.items()
    ]


def list_report_products() -> list[dict[str, str]]:
    """Report-page product list: configured products with a non-empty report: block."""
    config = load_product_config()
    if not config:
        return []
    return [
        {"product_id": primary_product_id(nick), "display_name": entry.get("display_name", nick)}
        for nick, entry in config.items()
        if is_report_enabled(nick)
    ]
