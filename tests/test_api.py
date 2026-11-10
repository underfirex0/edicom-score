from fastapi.testclient import TestClient
from edicom_score.api import create_app

def client(svc, key=None):
    svc.settings.api_key = key
    return TestClient(create_app(svc))

def test_health(svc):
    r = client(svc).get("/health"); assert r.status_code == 200 and r.json()["firms"] == len(svc.store)

def test_search_and_status(svc):
    c = client(svc)
    res = c.get("/v1/search", params={"q": "sonofet"}).json()
    assert res["count"] >= 1
    code = res["results"][0]["code"]
    s = c.get(f"/v1/companies/{code}/status").json()
    assert s["code"] == code and s["status"] in {"ACTIVE", "PROBABLE", "VERIFY", "INACTIVE"} and s["label"] and s["confidence"]
    assert c.get(f"/v1/companies/{code}").json()["score"]["cls"] in "ABCDE"

def test_pdf_endpoint(svc):
    r = client(svc).get("/v1/companies/MA3065770/report.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"

def test_404_and_422(svc):
    c = client(svc)
    assert c.get("/v1/companies/NOPE").status_code == 404
    assert c.get("/v1/companies/NOPE/report.pdf").status_code == 404
    assert c.get("/v1/search").status_code == 422

def test_api_key(svc):
    c = client(svc, key="secret")
    assert c.get("/v1/companies/MA3065770").status_code == 401
    assert c.get("/v1/companies/MA3065770", headers={"X-API-Key": "secret"}).status_code == 200
    assert c.get("/health").status_code == 200     # health stays open
    svc.settings.api_key = None
