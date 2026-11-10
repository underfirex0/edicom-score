"""Hosting-mode behaviour (Vercel): read-only, key mandatory, synchronous ZIP, assets in sync."""
import io, json, subprocess, sys, zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from edicom_score.api import create_app
from edicom_score.config import Settings
from edicom_score.service import ScoreService

ROOT = Path(__file__).resolve().parents[1]
MINI = Path(__file__).parent / "data" / "mini_store"

@pytest.fixture()
def hosted(tmp_path):
    s = Settings(store_dir=MINI, pdf_cache_dir=tmp_path / "pdf", read_only=True, require_key=True, api_key=None)
    return s, ScoreService(s)

def test_refuses_to_serve_without_key(hosted):
    s, svc = hosted; c = TestClient(create_app(svc))
    r = c.get("/v1/overview"); assert r.status_code == 503 and "EDICOM_API_KEY" in r.json()["detail"]
    assert c.get("/health").json()["status"] == "misconfigured"
    assert c.get("/v1/companies/MA3065770/report.pdf").status_code == 503

def test_key_required_and_constant_time(hosted):
    s, svc = hosted; s.api_key = "k3y"; c = TestClient(create_app(svc))
    assert c.get("/v1/overview").status_code == 401 and c.get("/v1/overview", headers={"X-API-Key": "nope"}).status_code == 401
    assert c.get("/v1/overview", headers={"X-API-Key": "k3y"}).status_code == 200
    h = c.get("/health").json(); assert h["status"] == "ok" and h["capabilities"] == {"import": False, "batch_async": False, "batch_max": 12}

def test_import_and_async_jobs_disabled(hosted):
    s, svc = hosted; s.api_key = "k"; c = TestClient(create_app(svc)); H = {"X-API-Key": "k"}
    assert c.post("/v1/import/scan", headers=H, files=[("files", ("a.xlsx", b"x", "application/octet-stream"))]).status_code == 403
    assert c.post("/v1/import/aaaaaaaaaaaa/build", headers=H).status_code == 403
    assert c.post("/v1/batch", headers=H, json={"codes": ["MA3065770"]}).status_code == 403

def test_sync_zip_and_limits(hosted):
    s, svc = hosted; s.api_key = "k"; c = TestClient(create_app(svc)); H = {"X-API-Key": "k"}
    r = c.post("/v1/batch.zip", headers=H, json={"codes": ["MA3065770", "MA9011330"]})
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip" and len(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == 2
    s.batch_max = 1; assert c.post("/v1/batch.zip", headers=H, json={"codes": ["MA3065770", "MA9011330"]}).status_code == 413
    s.batch_max = 12; s.zip_max_bytes = 100_000                      # a single PDF is bigger than this: must stop, not crash
    r = c.post("/v1/batch.zip", headers=H, json={"codes": ["MA3065770", "MA9011330"]}); assert r.status_code == 413 and "volumineuse" in r.json()["detail"]

def test_pdf_cache_goes_to_tmp_when_read_only(monkeypatch):
    monkeypatch.delenv("EDICOM_PDF_CACHE", raising=False)
    s = Settings(store_dir=MINI, read_only=True)
    assert str(s.pdf_cache_dir).startswith(("/tmp", "/var", "C:", "/private")) and MINI not in s.pdf_cache_dir.parents

def test_vercel_entrypoint_imports_and_serves(tmp_path, monkeypatch):
    monkeypatch.setenv("EDICOM_STORE_DIR", str(MINI)); monkeypatch.setenv("EDICOM_API_KEY", "k"); monkeypatch.setenv("VERCEL", "1")
    import importlib.util
    spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "api" / "index.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    c = TestClient(m.app); assert c.get("/v1/companies/MA3065770", headers={"X-API-Key": "k"}).status_code == 200

def test_vercel_json_valid_and_routes_cover_api():
    cfg = json.loads((ROOT / "vercel.json").read_text())
    assert cfg["functions"]["api/index.py"]["maxDuration"] <= 60
    srcs = [r["source"] for r in cfg["rewrites"]]
    assert "/v1/:path*" in srcs and "/health" in srcs and all(r["destination"] == "/api/index" for r in cfg["rewrites"])

def test_public_assets_in_sync_with_web():
    web = ROOT / "edicom_score" / "web"; pub = ROOT / "public"
    for f in web.rglob("*"):
        if f.is_file():
            dest = pub / "index.html" if f.name == "index.html" else pub / "static" / f.relative_to(web)
            assert dest.exists() and dest.read_bytes() == f.read_bytes(), f"{dest} is stale: run `python -m edicom_score vercel`"

def test_deploy_files_present_and_pinned():
    req = (ROOT / "requirements.txt").read_text()
    for pkg in ("pandas", "numpy", "matplotlib", "reportlab", "fastapi"): assert f"{pkg}==" in req
    assert "scikit-learn" not in req and (ROOT / ".python-version").exists() and (ROOT / "store" / "scores.pkl").exists()
    assert "tests" in (ROOT / ".vercelignore").read_text().split()
