"""Scores store: one pickle (the panel) + meta.json. Lookup by code / ICE / RC / name."""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path
import pandas as pd

PANEL = "scores.pkl"
META = "meta.json"

def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())

def _rc_str(v) -> str:
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        return str(v or "").strip()

def save(R: pd.DataFrame, meta: dict, store_dir) -> Path:
    d = Path(store_dir); d.mkdir(parents=True, exist_ok=True)
    meta = {**meta, "pandas_version": pd.__version__}
    R = R.copy(); R["_name_norm"] = R["E_Raison Sociale"].map(norm)
    R.to_pickle(d / PANEL)
    (d / META).write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return d

class Store:
    def __init__(self, store_dir):
        d = Path(store_dir)
        if not (d / PANEL).exists():
            raise FileNotFoundError(f"No scores store in {d} — run `edicom-score build` first.")
        self.meta: dict = json.loads((d / META).read_text(encoding="utf-8"))
        try:
            self.R: pd.DataFrame = pd.read_pickle(d / PANEL)
        except Exception as e:
            raise RuntimeError(f"Le fichier de scores a été créé avec pandas {self.meta.get('pandas_version', '?')} et ne se lit pas avec pandas {pd.__version__}. "
                               "Recalculez-le avec les versions de requirements.txt (python -m edicom_score build ...).") from e
        if "_name_norm" not in self.R:
            self.R["_name_norm"] = self.R["E_Raison Sociale"].map(norm)
        self._ice = self.R["E_ICE"].astype("string").str.replace(r"\D", "", regex=True)
        self._rc = self.R["E_RC"].map(_rc_str)

    def __len__(self): return len(self.R)

    def get(self, code: str):
        return self.R.loc[code] if code in self.R.index else None

    def find(self, *, ice=None, rc=None, city=None, name=None, limit=10) -> pd.DataFrame:
        R = self.R
        if ice:
            m = self._ice == re.sub(r"\D", "", str(ice)).zfill(15)
            return R[m.fillna(False)].head(limit)
        if rc:
            m = self._rc == _rc_str(rc)
            if city:
                m &= R["E_VILLE RC"].map(norm) == norm(city)
            return R[m.fillna(False)].head(limit)
        if name:
            q = norm(name)
            if not q: return R.iloc[0:0]
            toks = q.split()
            m = pd.Series(True, index=R.index)
            for t in toks:
                m &= R["_name_norm"].str.contains(t, regex=False)
            hit = R[m].copy()
            # rank: exact > prefix > shorter name
            hit["_rk"] = hit["_name_norm"].map(lambda n: (0 if n == q else 1 if n.startswith(q) else 2, len(n)))
            return hit.sort_values("_rk").drop(columns="_rk").head(limit)
        return R.iloc[0:0]

    def resolve(self, key: str):
        """Free-form key: code, ICE (15 digits), or exact name. Returns a row or None."""
        k = str(key).strip()
        r = self.get(k) if k else None
        if r is not None: return r
        digits = re.sub(r"\D", "", k)
        if len(digits) >= 10:
            h = self.find(ice=digits, limit=1)
            if len(h): return h.iloc[0]
        h = self.find(name=k, limit=1)
        return h.iloc[0] if len(h) else None

def summary_row(r) -> dict:
    """Compact JSON view of a firm (used by the API)."""
    def f(v):
        if v is None: return None
        try:
            if pd.isna(v): return None
        except Exception: pass
        return v.item() if hasattr(v, "item") else v
    return {
        "code": r.name, "name": f(r["E_Raison Sociale"]), "ice": f(r["E_ICE"]), "rc": _rc_str(r["E_RC"]) if f(r["E_RC"]) is not None else None,
        "city": f(r["E_VILLE RC"]), "legal_form": f(r["E_FORM.JUR"]), "created": f(r["E_ANNEE CREATION"]),
        "score": f(r["score"]), "class": f(r["classe"]), "perspective": f(r["perspective"]),
        "percentile": f(r["percentile"]), "reliability": f(r["fiabilite"]),
        "activity": {"status": f(r["act_code"]), "label": f(r["act_label"]), "confidence": f(r["act_conf"]),
                     "last_proof_year": f(r["act_last"]), "p_dormant": f(r["act_p_dorm"]), "reason": f(r["act_line"])},
        "pillars": {k: f(r[k]) for k in ("P1", "P2", "P3", "P4", "P5")},
        "fiscal_year": f(r["fy"]),
    }


# ---------------------------------------------------------------- filtering (shared by list, export, batch)
SORTS = {"score": "score", "name": "_name_norm", "city": "E_VILLE RC", "created": "E_ANNEE CREATION", "activity": "act_p_dorm", "percentile": "percentile"}

def _csv(v):
    return [x for x in (v.split(",") if isinstance(v, str) else (v or [])) if x != ""]

def filter_frame(R: pd.DataFrame, *, q=None, cls=None, activity=None, city=None, form=None, persp=None, smin=None, smax=None) -> pd.DataFrame:
    m = pd.Series(True, index=R.index)
    if q:
        digits = re.sub(r"\D", "", str(q))
        nq = norm(q)
        if len(digits) >= 4 and len(digits) >= len(str(q).replace(" ", "")) - 1:
            ice = R["E_ICE"].astype("string").str.replace(r"\D", "", regex=True)
            m &= ice.str.contains(digits, regex=False).fillna(False) | R.index.to_series().str.contains(str(q).strip(), case=False, regex=False)
        else:
            for t in nq.split():
                m &= R["_name_norm"].str.contains(t, regex=False) | R.index.to_series().str.lower().eq(t)
    if _csv(cls): m &= R["classe"].isin(_csv(cls))
    if _csv(activity): m &= R["act_code"].isin(_csv(activity))
    if _csv(persp): m &= R["perspective"].isin(_csv(persp))
    if _csv(city):
        want = {norm(c) for c in _csv(city)}; m &= R["E_VILLE RC"].map(norm).isin(want)
    if _csv(form): m &= R["E_FORM.JUR"].isin(_csv(form))
    if smin is not None: m &= R["score"] >= float(smin)
    if smax is not None: m &= R["score"] <= float(smax)
    return R[m]

def sort_frame(R: pd.DataFrame, sort="score", order="desc") -> pd.DataFrame:
    col = SORTS.get(sort, "score")
    return R.sort_values(col, ascending=(order == "asc"), na_position="last", kind="mergesort")

def light_row(r) -> dict:
    """Compact row for lists and suggestions."""
    def f(v):
        try:
            if pd.isna(v): return None
        except Exception: pass
        return v.item() if hasattr(v, "item") else v
    return {"code": r.name, "name": f(r["E_Raison Sociale"]), "city": f(r["E_VILLE RC"]), "form": f(r["E_FORM.JUR"]), "created": f(r["E_ANNEE CREATION"]),
            "ice": f(r["E_ICE"]), "score": f(r["score"]), "cls": f(r["classe"]), "persp": f(r["perspective"]),
            "act": f(r["act_code"]), "act_label": f(r["act_label"]), "act_conf": f(r["act_conf"])}
