"""Web app + JSON API.  Run: python -m edicom_score serve   ->   http://localhost:8000"""
from __future__ import annotations
import hmac, io, re, shutil, tempfile, uuid, zipfile
from pathlib import Path
import numpy as np, pandas as pd
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from . import __version__, activity as A, ingest, jobs, narrative as N, pipeline as PL, report as RP, scoring as S, store as ST
from .config import OBSERVED_ADVERSE_RATE, Settings, get_settings
from .service import ScoreService

WEB = Path(__file__).resolve().parent / "web"

def _j(v):
    """JSON-safe scalar."""
    if v is None: return None
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating, float)): return None if not np.isfinite(v) else float(v)
    if isinstance(v, (np.bool_,)): return bool(v)
    try:
        if pd.isna(v): return None
    except (TypeError, ValueError): pass
    return v

def _fix(o):
    if isinstance(o, dict): return {k: _fix(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_fix(v) for v in o]
    return _j(o)

def create_app(service: ScoreService | None = None) -> FastAPI:
    app = FastAPI(title="Edicom Score Entreprise", version=__version__,
                  description="Score de santé financière et statut d'activité des entreprises (Telecontact).")
    settings = service.settings if service else get_settings()
    state = {"svc": service}

    def svc() -> ScoreService:
        if state["svc"] is None:
            try: state["svc"] = ScoreService(settings)
            except FileNotFoundError: raise HTTPException(503, "no_store")
        return state["svc"]

    def auth(x_api_key: str | None = Header(default=None)):
        if settings.require_key and not settings.api_key:        # public hosting without a key would expose every company: fail closed
            raise HTTPException(503, "Déploiement non sécurisé : définissez la variable d'environnement EDICOM_API_KEY.")
        if settings.api_key and not hmac.compare_digest((x_api_key or "").encode(), settings.api_key.encode()):
            raise HTTPException(401, "Clé d'accès invalide ou absente")

    def writable():
        if settings.read_only:
            raise HTTPException(403, "Cette version en ligne est en lecture seule : importez les données en local, puis redéployez.")
    guard = [Depends(auth)]

    # ------------------------------------------------------------------ app shell
    @app.get("/", include_in_schema=False)
    def index(): return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})
    app.mount("/static", StaticFiles(directory=WEB), name="static")

    caps = lambda: {"import": not settings.read_only, "batch_async": not settings.read_only, "batch_max": settings.batch_max}

    @app.get("/health")
    def health():
        base = {"version": __version__, "auth": bool(settings.api_key), "capabilities": caps()}
        if settings.require_key and not settings.api_key: return {**base, "status": "misconfigured", "detail": "EDICOM_API_KEY manquante"}
        try: s = svc()
        except HTTPException: return {**base, "status": "empty"}
        m = s.store.meta
        return {**base, "status": "ok", "firms": len(s.store), "fiscal_year": m.get("fy"), "built_at": m.get("built_at")}

    # ------------------------------------------------------------------ overview
    @app.get("/v1/overview", dependencies=guard)
    def overview():
        s = svc(); R = s.store.R; m = s.store.meta
        sc = R[R.classe != "NR"]
        bins = list(range(0, 101, 10)); h = np.histogram(sc.score.dropna(), bins=bins)[0]
        hist = [{"lo": bins[i], "hi": bins[i + 1], "n": int(h[i])} for i in range(len(h))]
        g = R.assign(_city=R["E_VILLE RC"].fillna("Non renseignée")).groupby("_city")
        cities = pd.DataFrame({"n": g.size(), "avg": g.score.mean(), "active": g.act_code.apply(lambda x: (x == "ACTIVE").mean())}).sort_values("n", ascending=False).head(12)
        cross = pd.crosstab(R.classe, R.act_code)
        def cnt(**kw): return int(len(ST.filter_frame(R, **kw)))
        insights = [
            {"id": "ab_verify", "title": "Bien notées (A ou B) mais activité non confirmée", "hint": "Solides sur le papier : confirmer qu'elles travaillent encore.", "n": cnt(cls="A,B", activity="VERIFY"), "q": {"cls": "A,B", "activity": "VERIFY"}},
            {"id": "abc_inactive", "title": "Notées A, B ou C mais probablement inactives", "hint": "Bilan correct, mais aucun signe d'exploitation.", "n": cnt(cls="A,B,C", activity="INACTIVE"), "q": {"cls": "A,B,C", "activity": "INACTIVE"}},
            {"id": "e_active", "title": "En détresse (E) mais encore actives", "hint": "Exposition à éviter ou à garantir.", "n": cnt(cls="E", activity="ACTIVE"), "q": {"cls": "E", "activity": "ACTIVE"}},
            {"id": "degrading", "title": "En dégradation sur un an (classes A à C)", "hint": "Score en baisse d'au moins 7 points.", "n": cnt(cls="A,B,C", persp="En dégradation"), "q": {"cls": "A,B,C", "persp": "En dégradation"}},
        ]
        return _fix({"fy": m.get("fy"), "built_at": m.get("built_at"), "n_firms": len(R), "n_scorable": int(len(sc)),
                     "class_counts": {k: int((R.classe == k).sum()) for k in ["A", "B", "C", "D", "E", "NR"]},
                     "status_counts": {k: int((R.act_code == k).sum()) for k in ["ACTIVE", "PROBABLE", "VERIFY", "INACTIVE"]},
                     "median_score": float(sc.score.median()), "hist": hist,
                     "cross": {c: {a: int(cross.loc[c, a]) if (c in cross.index and a in cross.columns) else 0 for a in ["ACTIVE", "PROBABLE", "VERIFY", "INACTIVE"]} for c in ["A", "B", "C", "D", "E", "NR"]},
                     "cities": [{"city": c, "n": int(r.n), "avg": r.avg, "active": r.active} for c, r in cities.iterrows()],
                     "insights": insights, "recent_window": m.get("recent_window"), "backtest": m.get("backtest"), "adverse": OBSERVED_ADVERSE_RATE})

    @app.get("/v1/facets", dependencies=guard)
    def facets():
        R = svc().store.R
        c = R["E_VILLE RC"].dropna().astype(str).str.strip().value_counts()
        f = R["E_FORM.JUR"].dropna().astype(str).value_counts()
        return {"cities": [{"v": k, "n": int(v)} for k, v in c.items()], "forms": [{"v": k, "n": int(v)} for k, v in f.items()]}

    # ------------------------------------------------------------------ list / search
    def _filters(q, cls, activity, city, form, persp, smin, smax):
        return dict(q=q, cls=cls, activity=activity, city=city, form=form, persp=persp, smin=smin, smax=smax)

    @app.get("/v1/companies", dependencies=guard)
    def companies(q: str | None = None, cls: str | None = Query(None, alias="class"), activity: str | None = None, city: str | None = None,
                  form: str | None = None, persp: str | None = None, smin: float | None = None, smax: float | None = None,
                  sort: str = "score", order: str = "desc", page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=200)):
        R = svc().store.R
        df = ST.sort_frame(ST.filter_frame(R, **_filters(q, cls, activity, city, form, persp, smin, smax)), sort, order)
        total = len(df); sl = df.iloc[(page - 1) * size: page * size]
        return _fix({"total": total, "page": page, "size": size, "pages": max(1, -(-total // size)), "items": [ST.light_row(r) for _, r in sl.iterrows()]})

    @app.get("/v1/suggest", dependencies=guard)
    def suggest(q: str = Query(..., min_length=2), limit: int = Query(8, ge=1, le=20)):
        R = svc().store.R
        df = ST.filter_frame(R, q=q)
        nq = ST.norm(q)
        rk = df["_name_norm"].map(lambda n: (0 if n == nq else 1 if n.startswith(nq) else 2, len(n)))
        df = df.assign(_rk=rk).sort_values("_rk").head(limit)
        return _fix({"total": int(len(ST.filter_frame(R, q=q))), "items": [ST.light_row(r) for _, r in df.iterrows()]})

    @app.get("/v1/search", dependencies=guard)          # kept for integrations
    def search(q: str | None = None, ice: str | None = None, rc: str | None = None, city: str | None = None, limit: int = Query(10, ge=1, le=50)):
        if not (q or ice or rc): raise HTTPException(422, "Provide q, ice or rc")
        hits = svc().store.find(ice=ice, rc=rc, city=city, name=q, limit=limit)
        return _fix({"count": len(hits), "results": [ST.summary_row(r) for _, r in hits.iterrows()]})

    # ------------------------------------------------------------------ one company
    def _detail(code: str) -> dict:
        s = svc(); r = s.store.get(code)
        if r is None: raise HTTPException(404, "Entreprise inconnue")
        meta = s.store.meta; a = A.status(r, settings=settings); cls = r["classe"]
        ca = pd.to_numeric(r["E_CA"], errors="coerce")
        evid = [{"sign": sg, "text": t.replace("{CA}", N.dh(ca))} for sg, t in a["evidence"]]
        good, bad = N.drivers(r) if cls != "NR" else ([], [])
        med = meta.get("medians", {})
        fmt = {"headroom": N.pct, "autonomy": N.pct, "assoc": N.pct, "fr_ta": lambda v: N.pct(v, sign=True), "current": lambda v: N.n_fr(v, 2),
               "roa": lambda v: N.pct(v, 1, True), "re_ta": lambda v: N.pct(v, sign=True)}
        names = {"headroom": "Fonds propres / capital social", "autonomy": "Fonds propres / total bilan", "assoc": "Comptes d'associés / total bilan",
                 "fr_ta": "Fonds de roulement / total bilan", "current": "Liquidité générale", "roa": "Résultat net / total bilan", "re_ta": "Bénéfices cumulés / total bilan"}
        inds = [{"key": k, "label": names[k], "value": _j(r[k]), "text": (fmt[k](r[k]) if pd.notna(r[k]) else "n.d.").replace("−0 %", "0 %"), "median": _j(med.get(k)),
                 "median_text": fmt[k](med[k]) if med.get(k) is not None else None, "sub": _j(r.get("s_" + k))} for k in names]
        pill = [{"k": k, "name": S.PILLAR_NAMES[k] if k != "P4" else f"Dynamique ({int(r['pfy'])} → {int(r['fy'])})", "score": _j(r[k]), "weight": S.CONFIG["pillar_w"][k]} for k in ["P1", "P2", "P3", "P4", "P5"]]
        keys = [("TA", "Total bilan"), ("CP", "Capitaux propres"), ("capital", "Capital social"), ("RN", "Résultat net"), ("CLIENTS", "Clients"), ("STOCKS", "Stocks"), ("F1_fourn", "Fournisseurs")]
        figs = [{"label": n, "cur": _j(r.get(k + "_cur")), "prev": _j(r.get(k + "_prev")), "cur_text": N.dh(r.get(k + "_cur")), "prev_text": N.dh(r.get(k + "_prev"))} for k, n in keys]
        addr = " ".join(str(x) for x in (r.get("E_NUM. VOIE"), r.get("E_VOIE"), r.get("E_COMPLEM. VOIE")) if pd.notna(x) and str(x).strip())
        capped = bool(pd.notna(r.get("raw_score")) and pd.notna(r["score"]) and r["score"] < r["raw_score"] - 0.05)
        cap_note = None
        if capped:
            cap_note = ("Score plafonné à 30 : les capitaux propres sont négatifs." if r["CP_cur"] < 0 else
                        "Score plafonné à 45 : les capitaux propres sont inférieurs au quart du capital social (seuil d'alerte légal).")
        out = {"code": code, "name": r["E_Raison Sociale"], "form": r["E_FORM.JUR"], "city": r["E_VILLE RC"], "created": r["E_ANNEE CREATION"],
               "ice": r["E_ICE"], "rc": ST._rc_str(r["E_RC"]) if pd.notna(r["E_RC"]) else None, "phone": r["E_TEL 1"], "email": r["E_EMAIL"], "web": r["E_WEB"],
               "manager": r["E_Dirigeant"], "manager_role": r["E_Fonction"], "address": addr or None, "capital": r["E_CAPITAL"], "headcount": r["E_EFFECTIF"],
               "ca": ca, "ca_year": r["E_ANNEE CA"], "ca_band": r["E_GAME CA"], "in_edicom": bool(r["edicom_match"]),
               "score": {"value": r["score"], "cls": cls, "label": PL.CLASS_LABEL[cls][0], "risk": PL.CLASS_LABEL[cls][1], "percentile": r["percentile"],
                         "perspective": r["perspective"], "delta": r["delta"], "score_prev": r["score_prev"], "score_static": r["score_cur_static"],
                         "reliability": r["fiabilite"], "reliability_pts": r["fiabilite_pts"], "adverse": OBSERVED_ADVERSE_RATE.get(cls),
                         "capped": capped, "cap_note": cap_note, "scorable": bool(r["scorable"]), "n_firms": meta.get("n_scorable")},
               "pillars": pill, "indicators": inds, "figures": figs, "strengths": good, "watch": bad,
               "activity": {"status": a["code"], "label": a["label"], "confidence": a["confidence"], "last_proof": a["last_proof_year"], "p_dormant": a["p_dormant"],
                            "band": a["band"], "reason": a["line"], "evidence": evid},
               "reco": RP.reco_text(cls, a, r), "fy": r["fy"], "pfy": r["pfy"], "built_at": meta.get("built_at")}
        return _fix(out)

    @app.get("/v1/companies/{code}", dependencies=guard)
    def company(code: str): return _detail(code)

    @app.get("/v1/companies/{code}/status", dependencies=guard)
    def company_status(code: str):
        d = _detail(code); return {"code": code, "name": d["name"], "fiscal_year": d["fy"], **d["activity"]}

    @app.get("/v1/companies/{code}/report.pdf", dependencies=guard)
    def report(code: str, download: bool = False):
        try: b, fn = svc().pdf(code)
        except KeyError: raise HTTPException(404, "Entreprise inconnue")
        disp = "attachment" if download else "inline"
        return Response(b, media_type="application/pdf", headers={"Content-Disposition": f'{disp}; filename="{re.sub(r"[^A-Za-z0-9_.-]", "_", fn)}"'})

    # ------------------------------------------------------------------ exports
    @app.get("/v1/export.xlsx", dependencies=guard)
    def export(q: str | None = None, cls: str | None = Query(None, alias="class"), activity: str | None = None, city: str | None = None, form: str | None = None,
               persp: str | None = None, smin: float | None = None, smax: float | None = None, sort: str = "score", order: str = "desc"):
        from .export import export_xlsx
        s = svc(); df = ST.sort_frame(ST.filter_frame(s.store.R, **_filters(q, cls, activity, city, form, persp, smin, smax)), sort, order)
        if df.empty: raise HTTPException(404, "Aucune entreprise ne correspond aux filtres")
        buf = io.BytesIO(); export_xlsx(df, s.store.meta, buf)
        return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="Edicom_Scores_{len(df)}_entreprises.xlsx"'})

    def _batch_codes(body: dict) -> list[str]:
        R = svc().store.R
        if body.get("codes"): codes = [c for c in body["codes"] if c in R.index]
        else:
            f = body.get("filter") or {}
            df = ST.sort_frame(ST.filter_frame(R, q=f.get("q"), cls=f.get("class"), activity=f.get("activity"), city=f.get("city"), form=f.get("form"),
                                                persp=f.get("persp"), smin=f.get("smin"), smax=f.get("smax")), f.get("sort", "score"), f.get("order", "desc"))
            codes = df.index.tolist()
        if not codes: raise HTTPException(404, "Aucune entreprise à exporter")
        if len(codes) > settings.batch_max: raise HTTPException(413, f"Maximum {settings.batch_max} rapports par archive ({len(codes)} demandés) : affinez les filtres.")
        return codes

    @app.post("/v1/batch", dependencies=guard)
    def batch(body: dict):
        """body: {"codes": [...]} or {"filter": {...}} -> background job producing a ZIP of PDFs (local installs)."""
        if settings.read_only: raise HTTPException(403, "Utilisez /v1/batch.zip sur cette version en ligne.")
        s = svc(); codes = _batch_codes(body)
        zdir = Path(s.cache) / "zips"; zdir.mkdir(parents=True, exist_ok=True)
        def work(job: jobs.Job):
            path = zdir / f"{job.id}.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
                for i, c in enumerate(codes, 1):
                    b, fn = s.pdf(c); z.writestr(fn, b); job.update(i, f"Rapport {i} sur {len(codes)}")
            return {"file": str(path), "count": len(codes), "name": f"Rapports_Edicom_{len(codes)}.zip"}
        return jobs.start("batch", work, total=len(codes)).to_dict()

    @app.post("/v1/batch.zip", dependencies=guard)
    def batch_zip(body: dict):
        """Synchronous ZIP (works on serverless hosting). Stops with 413 if the archive would exceed the response-size cap."""
        s = svc(); codes = _batch_codes(body); buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for i, c in enumerate(codes, 1):
                b, fn = s.pdf(c); z.writestr(fn, b)
                if buf.tell() > settings.zip_max_bytes:
                    raise HTTPException(413, f"Archive trop volumineuse pour cet hébergement : {i} rapports tiennent au maximum. Sélectionnez moins d'entreprises, ou générez le lot en local.")
        return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="Rapports_Edicom_{len(codes)}.zip"'})

    # ------------------------------------------------------------------ jobs
    @app.get("/v1/jobs/{job_id}", dependencies=guard)
    def job(job_id: str):
        j = jobs.get(job_id)
        if j is None: raise HTTPException(404, "Tâche inconnue")
        d = j.to_dict()
        if isinstance(d["result"], dict) and "file" in d["result"]: d["result"] = {k: v for k, v in d["result"].items() if k != "file"}
        return d

    @app.get("/v1/jobs/{job_id}/download", dependencies=guard)
    def job_download(job_id: str):
        j = jobs.get(job_id)
        if j is None or j.status != "done" or not isinstance(j.result, dict) or "file" not in j.result: raise HTTPException(404, "Fichier indisponible")
        return FileResponse(j.result["file"], media_type="application/zip", filename=j.result["name"])

    # ------------------------------------------------------------------ import
    updir = Path(settings.store_dir) / "uploads"

    @app.post("/v1/import/scan", dependencies=guard + [Depends(writable)])
    async def import_scan(files: list[UploadFile] = File(...)):
        sid = uuid.uuid4().hex[:12]; d = updir / sid; d.mkdir(parents=True, exist_ok=True); paths = []
        for i, f in enumerate(files):
            name = re.sub(r"[^\w.\- ]", "_", Path(f.filename or f"fichier{i}.xlsx").name)
            p = d / f"{i}_{name}"; p.write_bytes(await f.read()); paths.append(p)
        P = ingest.plan(paths)
        for s_ in P.sheets: s_.file = re.sub(r"^\d+_", "", s_.file)
        P.files = [re.sub(r"^\d+_", "", x) for x in P.files]
        out = P.to_dict(); out["id"] = sid
        return out

    @app.post("/v1/import/{sid}/build", dependencies=guard + [Depends(writable)])
    def import_build(sid: str):
        if not re.fullmatch(r"[0-9a-f]{12}", sid) or not (updir / sid).is_dir(): raise HTTPException(404, "Import introuvable : déposez à nouveau les fichiers")
        d = updir / sid; P = ingest.plan(sorted(d.iterdir()))
        if not P.ready: raise HTTPException(422, " ".join(P.errors))
        def work(job: jobs.Job):
            job.update(0, "Lecture des fichiers")
            ed, ac, pc, ap, pp, fy = ingest.load(P)
            R, meta = PL.build_from_frames(ed, ac, pc, ap, pp, fy, settings, progress=lambda i, label: job.update(i, label))
            job.update(4, "Enregistrement")
            ST.save(R, meta, settings.store_dir)
            state["svc"] = ScoreService(settings)
            shutil.rmtree(d, ignore_errors=True)
            return {"fy": fy, "n_firms": meta["n_firms"], "class_counts": meta["class_counts"], "status_counts": meta["status_counts"]}
        return jobs.start("import", work, total=5).to_dict()
    return app

app = create_app()
