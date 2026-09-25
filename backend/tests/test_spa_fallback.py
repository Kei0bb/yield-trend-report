"""SPA fallback route (app.main:spa_fallback) — path traversal guard.

main.py derives FRONTEND_DIST from its own __file__, so to control what's
"inside" the served dist we load a fresh copy of app.main from a fake
location under tmp_path/backend/app/main.py. This keeps FRONTEND_DIST
rooted at tmp_path/frontend/dist without touching the real frontend/dist,
and without needing to reload/monkeypatch the already-imported real module
(other test files import app.main too, so we restore sys.modules afterward).
"""

import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REAL_MAIN = Path(__file__).resolve().parents[1] / "app" / "main.py"


def _load_main_with_dist(tmp_path: Path):
    fake_main = tmp_path / "backend" / "app" / "main.py"
    fake_main.parent.mkdir(parents=True)
    fake_main.write_text(REAL_MAIN.read_text())

    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa index</html>")
    (dist / "favicon.svg").write_text("<svg>legit favicon</svg>")

    # Lives outside FRONTEND_DIST (two levels up: dist -> frontend -> tmp_path).
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET - outside frontend/dist")

    spec = importlib.util.spec_from_file_location("app.main", fake_main)
    module = importlib.util.module_from_spec(spec)
    original = sys.modules.get("app.main")
    sys.modules["app.main"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        _restore(original)
        raise
    return module, original, secret


def _restore(original):
    if original is not None:
        sys.modules["app.main"] = original
    else:
        sys.modules.pop("app.main", None)


def test_spa_fallback_blocks_path_traversal(tmp_path):
    """GET /..%2f..%2fsecret.txt must not leak a file outside FRONTEND_DIST.

    The ".." segments are hidden behind a percent-encoded slash (%2f) so
    they survive dot-segment normalization done on literal "/" boundaries,
    then get decoded into real ".." by the time they reach spa_fallback's
    full_path.
    """
    module, original, secret = _load_main_with_dist(tmp_path)
    try:
        client = TestClient(module.app)
        resp = client.get("/..%2f..%2fsecret.txt")
        assert secret.read_text() not in resp.text
        # Falls through to the SPA index instead of a 404.
        assert "spa index" in resp.text
    finally:
        _restore(original)


def test_spa_fallback_still_serves_real_root_files(tmp_path):
    module, original, _secret = _load_main_with_dist(tmp_path)
    try:
        client = TestClient(module.app)
        resp = client.get("/favicon.svg")
        assert resp.status_code == 200
        assert "legit favicon" in resp.text
    finally:
        _restore(original)


def test_spa_fallback_serves_index_for_unknown_route(tmp_path):
    module, original, _secret = _load_main_with_dist(tmp_path)
    try:
        client = TestClient(module.app)
        resp = client.get("/some/unknown/route")
        assert resp.status_code == 200
        assert "spa index" in resp.text
    finally:
        _restore(original)


def test_spa_index_is_not_cached(tmp_path):
    """index.html must be revalidated on every load; otherwise browsers keep a
    stale copy pointing at old hashed bundles after a rebuild."""
    module, original, _secret = _load_main_with_dist(tmp_path)
    try:
        client = TestClient(module.app)
        resp = client.get("/wafermap")
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-cache"
    finally:
        _restore(original)
