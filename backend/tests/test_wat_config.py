import json

from app.services.product_config import _parse_wat_pairs, resolve_wat_pairs


def test_parse_wat_pairs_reads_labels_and_items():
    raw = {
        "pairs": [
            {"label": "Core RVT",
             "vth": {"n": "VTHN_RVT", "p": "VTHP_RVT"},
             "idsat": {"n": "IDSATN_RVT", "p": "IDSATP_RVT"}},
        ]
    }
    pairs = _parse_wat_pairs(raw, "prod_a")
    assert pairs == [{
        "label": "Core RVT",
        "vth_n": "VTHN_RVT", "vth_p": "VTHP_RVT",
        "idsat_n": "IDSATN_RVT", "idsat_p": "IDSATP_RVT",
    }]


def test_parse_wat_pairs_preserves_declaration_order():
    raw = {"pairs": [
        {"label": "B", "vth": {"n": "a", "p": "b"}, "idsat": {"n": "c", "p": "d"}},
        {"label": "A", "vth": {"n": "e", "p": "f"}, "idsat": {"n": "g", "p": "h"}},
    ]}
    assert [p["label"] for p in _parse_wat_pairs(raw, "prod_a")] == ["B", "A"]


def test_parse_wat_pairs_skips_incomplete_entry(caplog):
    raw = {"pairs": [
        {"label": "Broken", "vth": {"n": "VTHN"}, "idsat": {"n": "I", "p": "J"}},
        {"label": "Good", "vth": {"n": "a", "p": "b"}, "idsat": {"n": "c", "p": "d"}},
    ]}
    with caplog.at_level("WARNING"):
        pairs = _parse_wat_pairs(raw, "prod_a")
    assert [p["label"] for p in pairs] == ["Good"]
    assert "Broken" in caplog.text


def test_parse_wat_pairs_missing_block_returns_empty():
    assert _parse_wat_pairs(None, "prod_a") == []
    assert _parse_wat_pairs({}, "prod_a") == []
    assert _parse_wat_pairs({"pairs": "not-a-list"}, "prod_a") == []


def test_parse_wat_pairs_defaults_label_when_absent():
    raw = {"pairs": [{"vth": {"n": "a", "p": "b"}, "idsat": {"n": "c", "p": "d"}}]}
    assert _parse_wat_pairs(raw, "prod_a")[0]["label"] == "pair1"


def test_resolve_wat_pairs_unknown_nickname_is_empty():
    assert resolve_wat_pairs("__no_such_product__") == []


def test_resolve_wat_pairs_parses_stored_json(monkeypatch):
    import app.services.product_config as pc
    stored = json.dumps([{"label": "X", "vth_n": "a", "vth_p": "b",
                          "idsat_n": "c", "idsat_p": "d"}])
    monkeypatch.setattr(pc, "load_product_config", lambda: {"p": {"wat": stored}})
    assert pc.resolve_wat_pairs("p")[0]["label"] == "X"
