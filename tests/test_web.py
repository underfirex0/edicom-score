import io, time
import pandas as pd
from fastapi.testclient import TestClient
from edicom_score.api import create_app
from edicom_score.config import Settings
from edicom_score.service import ScoreService

def client(svc): svc.settings.api_key = None; return TestClient(create_app(svc))

def test_index_and_assets(svc):
    c = client(svc); r = c.get("/")
    assert r.status_code == 200 and "Edicom" in r.text and "/static/app.js" in r.text
    for f in ("app.js", "app.css", "fonts/bricolage-grotesque-latin-wght-normal.woff2"): assert c.get("/static/" + f).status_code == 200

def test_overview(svc):
    o = client(svc).get("/v1/overview").json()
    assert o["n_firms"] == len(svc.store) and sum(o["class_counts"].values()) == o["n_firms"] and sum(o["status_counts"].values()) == o["n_firms"]
    assert len(o["hist"]) == 10 and all(i["n"] >= 0 for i in o["insights"])

def test_list_filters_sort_pagination(svc):
    c = client(svc)
    d = c.get("/v1/companies", params={"class": "A,B", "size": 5}).json()
    assert d["total"] > 0 and len(d["items"]) <= 5 and all(i["cls"] in "AB" for i in d["items"])
    sc = [i["score"] for i in d["items"]]; assert sc == sorted(sc, reverse=True)
    asc = c.get("/v1/companies", params={"sort": "score", "order": "asc", "class": "A,B,C,D,E"}).json()["items"]
    assert [i["score"] for i in asc] == sorted(i["score"] for i in asc)
    assert c.get("/v1/companies", params={"activity": "INACTIVE"}).json()["total"] == int((svc.store.R.act_code == "INACTIVE").sum())
    assert c.get("/v1/companies", params={"q": "zzzzqq"}).json()["total"] == 0
    assert c.get("/v1/companies", params={"smin": 90}).json()["total"] == int((svc.store.R.score >= 90).sum())

def test_suggest_and_detail(svc):
    c = client(svc); s = c.get("/v1/suggest", params={"q": "sonofet"}).json()
    assert s["items"][0]["code"] == "MA3065770"
    d = c.get("/v1/companies/MA3348858").json()          # capped, 'à vérifier' firm
    assert d["score"]["capped"] and d["activity"]["status"] == "VERIFY" and len(d["pillars"]) == 5 and d["indicators"] and d["reco"]
    nr = c.get("/v1/companies/" + svc.store.R[svc.store.R.classe == "NR"].index[0]).json()
    assert nr["score"]["cls"] == "NR" and nr["strengths"] == []

def test_export_xlsx(svc):
    r = client(svc).get("/v1/export.xlsx", params={"class": "E"})
    df = pd.read_excel(io.BytesIO(r.content)); assert r.status_code == 200 and len(df) == int((svc.store.R.classe == "E").sum()) and set(df["Classe"]) == {"E"}
    assert client(svc).get("/v1/export.xlsx", params={"q": "zzzzqq"}).status_code == 404

def test_batch_zip_job(svc):
    c = client(svc); codes = ["MA3065770", "MA9011330"]
    j = c.post("/v1/batch", json={"codes": codes}).json()
    for _ in range(100):
        j = c.get("/v1/jobs/" + j["id"]).json()
        if j["status"] != "running": break
        time.sleep(0.2)
    assert j["status"] == "done" and j["result"]["count"] == 2 and "file" not in j["result"]
    import zipfile; z = zipfile.ZipFile(io.BytesIO(c.get(f"/v1/jobs/{j['id']}/download").content)); assert len(z.namelist()) == 2 and all(n.endswith(".pdf") for n in z.namelist())

def test_batch_limit(svc):
    old = svc.settings.batch_max; svc.settings.batch_max = 3
    try: assert client(svc).post("/v1/batch", json={"filter": {}}).status_code == 413
    finally: svc.settings.batch_max = old

def test_import_scan_and_errors(svc, tmp_path):
    c = client(svc)
    r = c.post("/v1/import/scan", files=[("files", ("notes.xlsx", b"not excel", "application/octet-stream"))]).json()
    assert r["ready"] is False and r["errors"]
    assert c.post("/v1/import/zzzzzzzzzzzz/build").status_code == 404
    assert c.post("/v1/import/../build").status_code in (404, 405)

def test_empty_store_behaviour(tmp_path):
    import os; os.environ["EDICOM_STORE_DIR"] = str(tmp_path / "none")
    c = TestClient(create_app()); h = c.get("/health").json(); assert h["status"] == "empty"
    assert c.get("/v1/overview").status_code == 503
    del os.environ["EDICOM_STORE_DIR"]

def test_full_import_roundtrip(tmp_path):
    """Upload the single workbook, build, then query — only runs when the raw data is available."""
    import os, pytest
    raw = os.getenv("EDICOM_RAW_DIR")
    if not raw: pytest.skip("EDICOM_RAW_DIR not set")
    from pathlib import Path
    from edicom_score import loaders, features
    d = Path(raw); f = lambda pat: next(d.glob(pat))
    wb = tmp_path / "all.xlsx"
    with pd.ExcelWriter(wb) as w:
        for y, pat in ((2018, "*OMPIC_2018.xlsx"), (2019, "*OMPIC_2019.xlsx")):
            a, p = loaders.read_ompic(f(pat), y); features.merge_year(a, p).to_excel(w, sheet_name=str(y), index=False)
        pd.read_excel(f("*Firmes_Edicom*.xlsx")).to_excel(w, sheet_name="Edicom", index=False)
    os.environ["EDICOM_STORE_DIR"] = str(tmp_path / "store")
    try:
        c = TestClient(create_app())
        scan = c.post("/v1/import/scan", files=[("files", ("all.xlsx", wb.read_bytes(), "application/octet-stream"))]).json()
        assert scan["ready"] and scan["fy"] == 2019
        j = c.post(f"/v1/import/{scan['id']}/build").json()
        for _ in range(200):
            j = c.get("/v1/jobs/" + j["id"]).json()
            if j["status"] != "running": break
            time.sleep(0.2)
        assert j["status"] == "done" and j["result"]["n_firms"] == 3787 and j["result"]["class_counts"]["A"] == 1141
        assert c.get("/v1/overview").json()["n_firms"] == 3787
    finally:
        del os.environ["EDICOM_STORE_DIR"]
