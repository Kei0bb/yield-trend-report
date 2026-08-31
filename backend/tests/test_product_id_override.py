"""Per-process PRODUCT_ID overrides.

SLT reads the FT schema, whose PRODUCT_ID appends a package number
(SC0G29B -> SC0G29BP3-ES), so it cannot share CP's id.
"""

import pytest

from app.services import product_config
from app.services.product_config import resolve_product_ids
from app.services.yield_queries import build_product_id_where

BASE = {
    "display_name": "Draco",
    "product_id": "SC0G29B",
    "bin_group": "main",
}


@pytest.fixture
def config(monkeypatch):
    """Install a one-product config; the loader is lru_cached, so patch the getter."""
    def install(**over):
        entry = {**BASE, "cp_product_id": "", "ft_product_id": "", "slt_product_id": "", **over}
        monkeypatch.setattr(product_config, "load_product_config", lambda: {"Draco": entry})
    return install


def test_process_without_override_uses_the_shared_id(config):
    config()
    assert resolve_product_ids("Draco", "CP") == ["SC0G29B"]
    assert resolve_product_ids("Draco", "SLT") == ["SC0G29B"]
    assert resolve_product_ids("Draco") == ["SC0G29B"]


def test_slt_override_applies_only_to_slt(config):
    config(slt_product_id="SC0G29B%")
    assert resolve_product_ids("Draco", "SLT") == ["SC0G29B%"]
    assert resolve_product_ids("Draco", "CP") == ["SC0G29B"]
    assert resolve_product_ids("Draco", "FT") == ["SC0G29B"]
    assert resolve_product_ids("Draco") == ["SC0G29B"], "no process → shared id"


def test_override_does_not_fall_back_across_processes(config):
    """SLT and FT read different tables; inheriting FT's id would be wrong."""
    config(ft_product_id="SC0G29B-FT")
    assert resolve_product_ids("Draco", "SLT") == ["SC0G29B"]


def test_override_accepts_a_list(config):
    config(slt_product_id="SC0G29BP3-ES;SC0G29BP3-CS")
    assert resolve_product_ids("Draco", "SLT") == ["SC0G29BP3-ES", "SC0G29BP3-CS"]


def test_wildcard_override_becomes_a_like_predicate(config):
    """The '%' is what absorbs new package numbers without a config edit."""
    config(slt_product_id="SC0G29B%")
    where, binds = build_product_id_where(resolve_product_ids("Draco", "SLT"))
    assert where == "h.PRODUCT_ID LIKE :like0"
    assert binds == {"like0": "SC0G29B%"}


def test_yaml_product_ids_block_is_parsed(tmp_path, monkeypatch):
    """End-to-end through the YAML loader, including the list form."""
    yaml_file = tmp_path / "product_config.yaml"
    yaml_file.write_text(
        "products:\n"
        "  Draco:\n"
        "    product_id: SC0G29B\n"
        "    product_ids:\n"
        "      slt: [SC0G29BP3-ES, SC0G29BP3-CS]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(product_config, "PRODUCT_CONFIG_YAML", yaml_file)
    product_config.load_product_config.cache_clear()
    try:
        assert resolve_product_ids("Draco", "SLT") == ["SC0G29BP3-ES", "SC0G29BP3-CS"]
        assert resolve_product_ids("Draco", "CP") == ["SC0G29B"]
    finally:
        product_config.load_product_config.cache_clear()
