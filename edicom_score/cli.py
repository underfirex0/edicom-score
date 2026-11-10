"""Command line: edicom-score build | status | pdf | batch | export | serve."""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path
import pandas as pd
from .config import Settings
from . import __version__

def _settings(a) -> Settings:
    s = Settings()
    if getattr(a, "store", None): s = Settings(store_dir=a.store)
    return s

def cmd_build(a):
    from . import ingest, pipeline, store
    s = _settings(a); t = time.time()
    if a.files:
        P = ingest.plan(a.files)
        for w in P.warnings: print("Attention :", w)
        if not P.ready: sys.exit("Import impossible :\n  - " + "\n  - ".join(P.errors))
        ed, ac, pc, ap, pp, fy = ingest.load(P)
        R, meta = pipeline.build_from_frames(ed, ac, pc, ap, pp, fy, s)
    else:
        if not (a.ompic_cur and a.ompic_prev and a.fy and a.edicom): sys.exit("Give the Excel file(s) to import, or --ompic-cur/--ompic-prev/--fy/--edicom")
        R, meta = pipeline.build_scores(pipeline.BuildInputs(a.ompic_cur, a.ompic_prev, a.fy, a.edicom), s)
    store.save(R, meta, s.store_dir)
    print(f"Built {len(R):,} firms (FY{meta['fy']}) in {time.time()-t:.1f}s -> {s.store_dir}")
    print("Classes :", meta["class_counts"]); print("Statuts :", meta["status_counts"])

def _svc(a):
    from .service import ScoreService
    return ScoreService(_settings(a))

def cmd_status(a):
    s = _svc(a).store; r = s.resolve(a.key)
    if r is None: sys.exit(f"Not found: {a.key}")
    from .store import summary_row
    import json; print(json.dumps(summary_row(r), ensure_ascii=False, indent=1))

def cmd_pdf(a):
    sv = _svc(a); r = sv.store.resolve(a.key)
    if r is None: sys.exit(f"Not found: {a.key}")
    b, fn = sv.pdf(r.name); out = Path(a.out or fn); out.write_bytes(b); print(out)

def cmd_batch(a):
    sv = _svc(a); R = sv.store.R
    if a.codes: codes = [c.strip() for c in Path(a.codes).read_text().split() if c.strip()]
    else:
        m = pd.Series(True, index=R.index)
        if a.cls: m &= R.classe.isin(a.cls.split(","))
        if a.activity: m &= R.act_code.isin(a.activity.split(","))
        codes = R[m].index.tolist()
    if a.limit: codes = codes[: a.limit]
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True); t = time.time()
    for i, c in enumerate(codes, 1):
        b, fn = sv.pdf(c); (out / fn).write_bytes(b)
        if i % 50 == 0: print(f"{i}/{len(codes)}", flush=True)
    print(f"{len(codes)} PDFs -> {out} ({time.time()-t:.0f}s)")

def cmd_export(a):
    from .export import export_xlsx
    sv = _svc(a); export_xlsx(sv.store.R, sv.store.meta, a.out); print(a.out)

def cmd_vercel(a):
    """Prepare ./store (scores) and ./public (web assets) so the folder can be deployed with `vercel --prod`."""
    import shutil
    from . import ingest, pipeline, store
    root = Path(a.project).resolve()
    if not (root / "vercel.json").exists(): sys.exit(f"vercel.json introuvable dans {root} : lancez la commande depuis le dossier du projet.")
    web = Path(__file__).resolve().parent / "web"; pub = root / "public"
    for f in web.rglob("*"):
        if f.is_file():
            dest = pub / "index.html" if f.name == "index.html" else pub / "static" / f.relative_to(web)
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, dest)
    dst = root / "store"
    if a.files:
        P = ingest.plan(a.files)
        if not P.ready: sys.exit("Import impossible :\n  - " + "\n  - ".join(P.errors))
        ed, ac, pc, ap, pp, fy = ingest.load(P)
        R, meta = pipeline.build_from_frames(ed, ac, pc, ap, pp, fy, _settings(a)); store.save(R, meta, dst)
    else:
        src = Path(a.store) if a.store else _settings(a).store_dir
        if not (src / store.PANEL).exists(): sys.exit(f"Aucun score dans {src} : importez d'abord vos fichiers (page Données) ou donnez-les en argument.")
        if src.resolve() != dst.resolve():
            dst.mkdir(parents=True, exist_ok=True)
            for n in (store.PANEL, store.META): shutil.copy2(src / n, dst / n)
    size = sum(f.stat().st_size for f in dst.iterdir() if f.is_file()) / 1e6
    meta = store.Store(dst).meta
    print(f"Prêt : {meta['n_firms']:,} entreprises (exercice {meta['fy']}), {size:.1f} Mo dans {dst}")
    print("Étapes suivantes :\n  1. vercel env add EDICOM_API_KEY      (obligatoire : sans clé, le site refuse de servir les données)\n  2. vercel --prod")

def cmd_serve(a):
    import uvicorn
    import os
    if a.store: os.environ["EDICOM_STORE_DIR"] = str(a.store)
    url = f"http://{'localhost' if a.host in ('127.0.0.1', '0.0.0.0') else a.host}:{a.port}"
    print(f"Edicom Score Entreprise : {url}   (Ctrl+C pour arrêter)")
    if not a.no_browser:
        import threading, webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("edicom_score.api:app", host=a.host, port=a.port, log_level="warning")

def main(argv=None):
    p = argparse.ArgumentParser("edicom-score", description="Edicom Score Entreprise — score financier + statut d'activité")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--store", help="Store directory (default: $EDICOM_STORE_DIR or ./output)")
    sp = p.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build", help="Compute scores from Excel files (one workbook with sheets 2018/2019/Edicom, or the separate files)")
    b.add_argument("files", nargs="*", help="Excel file(s); sheets, years and the Edicom base are detected automatically")
    b.add_argument("--ompic-cur", help="(explicit mode) OMPIC file of the latest year")
    b.add_argument("--ompic-prev", help="(explicit mode) OMPIC file of the previous year")
    b.add_argument("--fy", type=int, help="(explicit mode) latest fiscal year")
    b.add_argument("--edicom", help="(explicit mode) Edicom firms file")
    b.set_defaults(f=cmd_build)
    s = sp.add_parser("status", help="Show score + activity status (key = code, ICE or name)"); s.add_argument("key"); s.set_defaults(f=cmd_status)
    d = sp.add_parser("pdf", help="Generate one PDF (key = code, ICE or name)"); d.add_argument("key"); d.add_argument("-o", "--out"); d.set_defaults(f=cmd_pdf)
    bt = sp.add_parser("batch", help="Generate many PDFs")
    bt.add_argument("--out-dir", default="output/pdfs"); bt.add_argument("--codes", help="text file with codes"); bt.add_argument("--cls", help="e.g. A,B")
    bt.add_argument("--activity", help="e.g. ACTIVE,PROBABLE"); bt.add_argument("--limit", type=int); bt.set_defaults(f=cmd_batch)
    e = sp.add_parser("export", help="Export the panel to xlsx"); e.add_argument("-o", "--out", default="output/scores.xlsx"); e.set_defaults(f=cmd_export)
    vc = sp.add_parser("vercel", help="Prepare the project folder for Vercel (scores + web assets)")
    vc.add_argument("files", nargs="*", help="optional Excel file(s) to compute from; otherwise the current store is copied")
    vc.add_argument("--project", default=".", help="project folder (contains vercel.json)"); vc.set_defaults(f=cmd_vercel)
    sv = sp.add_parser("serve", help="Start the HTTP API"); sv.add_argument("--host", default="127.0.0.1"); sv.add_argument("--port", type=int, default=8000); sv.add_argument("--no-browser", action="store_true", help="do not open the browser"); sv.set_defaults(f=cmd_serve)
    a = p.parse_args(argv); a.f(a)

if __name__ == "__main__":
    main()
