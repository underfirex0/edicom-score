def test_search_by_name_is_accent_and_case_insensitive(svc):
    h = svc.store.find(name="SONOFET")
    assert len(h) >= 1 and h.iloc[0]["E_Raison Sociale"].lower().startswith("sonofet")

def test_search_by_ice_and_rc(svc):
    r = svc.store.get("MA9011330")
    assert svc.store.find(ice=r["E_ICE"]).index.tolist()[0] == "MA9011330"
    assert "MA9011330" in svc.store.find(rc=r["E_RC"], city=r["E_VILLE RC"]).index

def test_resolve_by_code_ice_name(svc):
    r = svc.store.get("MA3065770")
    for key in ("MA3065770", r["E_ICE"], "Sonofet"):
        assert svc.store.resolve(key).name == "MA3065770"
    assert svc.store.resolve("zzz-unknown-zzz") is None

def test_pdf_cache(svc):
    b1, fn = svc.pdf("MA3065770"); b2, _ = svc.pdf("MA3065770")
    assert b1[:4] == b"%PDF" and b1 == b2 and fn.endswith(".pdf")

def test_every_status_and_class_renders(svc):
    R = svc.store.R
    picks = list(R.groupby("act_code").head(1).index) + list(R.groupby("classe").head(1).index)
    for c in dict.fromkeys(picks):
        assert svc.pdf(c)[0][:4] == b"%PDF"

def test_nr_firm_renders_single_page(svc):
    import io
    from pypdf import PdfReader
    nr = svc.store.R[svc.store.R.classe == "NR"].index[0]
    assert len(PdfReader(io.BytesIO(svc.pdf(nr)[0])).pages) == 1
