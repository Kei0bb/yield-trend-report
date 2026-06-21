import textwrap

import app.services.product_config as product_config
from app.services.product_config import (
    load_product_config,
    resolve_report_unit,
    resolve_report_units,
)


def _write_config(tmp_path, monkeypatch, yaml_text: str):
    """Point PRODUCT_CONFIG_YAML at a temp file with the given contents and
    clear the lru_cache so load_product_config() re-parses it."""
    cfg_path = tmp_path / "product_config.yaml"
    cfg_path.write_text(textwrap.dedent(yaml_text), encoding="utf-8")
    monkeypatch.setattr(product_config, "PRODUCT_CONFIG_YAML", cfg_path)
    load_product_config.cache_clear()


def test_explicit_report_units_parsed_in_order(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, """
        products:
          Phoenix:
            product_id: SCT101A
            bin_group: Phoenix
            processes:
              cp: [CP, CP1, CP2]
              ft: {subs: [cFT1]}
            report:
              - {family: cp, label: "CP",   values: [CP]}
              - {family: cp, label: "CP1",  values: [CP1]}
              - {family: ft, label: "cFT1", values: [cFT1]}
        """)

    units = resolve_report_units("Phoenix")
    assert units == [
        {"family": "CP", "label": "CP", "values": ["CP"]},
        {"family": "CP", "label": "CP1", "values": ["CP1"]},
        {"family": "FT", "label": "cFT1", "values": ["cFT1"]},
    ]
    load_product_config.cache_clear()


def test_family_is_upper_cased(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, """
        products:
          Phoenix:
            product_id: SCT101A
            report:
              - {family: slt, label: "cSLT1", values: [cSLT1]}
        """)

    units = resolve_report_units("Phoenix")
    assert units == [{"family": "SLT", "label": "cSLT1", "values": ["cSLT1"]}]
    load_product_config.cache_clear()


def test_scalar_values_wrapped_into_list(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, """
        products:
          Phoenix:
            product_id: SCT101A
            report:
              - {family: cp, label: "CP", values: CP}
        """)

    units = resolve_report_units("Phoenix")
    assert units == [{"family": "CP", "label": "CP", "values": ["CP"]}]
    load_product_config.cache_clear()


def test_malformed_entries_skipped(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, """
        products:
          Phoenix:
            product_id: SCT101A
            report:
              - {family: cp, label: "CP", values: [CP]}
              - {label: "Missing family", values: [CP1]}
              - {family: cp, values: [CP2]}
              - {family: cp, label: "Empty values", values: []}
        """)

    units = resolve_report_units("Phoenix")
    assert units == [{"family": "CP", "label": "CP", "values": ["CP"]}]
    load_product_config.cache_clear()


def test_resolve_report_unit_finds_by_label(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, """
        products:
          Phoenix:
            product_id: SCT101A
            report:
              - {family: cp, label: "CP",   values: [CP]}
              - {family: cp, label: "CP1",  values: [CP1]}
              - {family: ft, label: "cFT1", values: [cFT1]}
        """)

    unit = resolve_report_unit("Phoenix", "CP1")
    assert unit == {"family": "CP", "label": "CP1", "values": ["CP1"]}
    load_product_config.cache_clear()


def test_resolve_report_unit_unknown_label_returns_none(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, """
        products:
          Phoenix:
            product_id: SCT101A
            report:
              - {family: cp, label: "CP", values: [CP]}
        """)

    assert resolve_report_unit("Phoenix", "DoesNotExist") is None
    load_product_config.cache_clear()


def test_fallback_when_no_report_key(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, """
        products:
          Product-A:
            product_id: P12345-A
            bin_group: main
            processes:
              ft: cFT1
              slt: cSLT1
        """)

    units = resolve_report_units("Product-A")
    assert units == [
        {"family": "CP", "label": "CP", "values": None},
        {"family": "FT", "label": "FT", "values": None},
        {"family": "SLT", "label": "SLT", "values": None},
    ]
    load_product_config.cache_clear()


def test_fallback_when_unconfigured_nickname(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, """
        products:
          Product-A:
            product_id: P12345-A
        """)

    units = resolve_report_units("SomeUnknownNickname")
    assert units == [
        {"family": "CP", "label": "CP", "values": None},
        {"family": "FT", "label": "FT", "values": None},
        {"family": "SLT", "label": "SLT", "values": None},
    ]
    load_product_config.cache_clear()
