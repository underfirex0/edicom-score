"""End-to-end build: raw workbooks -> scored panel (score, class, perspective, reliability, activity status)."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
import numpy as np, pandas as pd
from . import loaders, features, scoring as S, activity as A
from .config import OBSERVED_ADVERSE_RATE, PANEL_BACKTEST_LABEL, Settings

CLASSES = [(75, "A", "Très solide", "Risque très faible"), (60, "B", "Solide", "Risque faible"), (45, "C", "Vigilance", "Risque modéré"),
           (30, "D", "Fragile", "Risque élevé"), (0, "E", "Détresse", "Risque très élevé")]
CLASS_LABEL = {l: (n, r) for _, l, n, r in CLASSES}; CLASS_LABEL["NR"] = ("Non noté", "Données insuffisantes")
RECO = {"A": "Conditions de paiement standard (jusqu'à 60 jours, délai légal par défaut — loi 69-21).",
        "B": "Conditions standard ; revue annuelle des comptes.",
        "C": "Encours plafonné, paiement à 30 jours, revue semestrielle ; privilégier les moyens de paiement sécurisés.",
        "D": "Acompte significatif ou garantie (aval, assurance-crédit) exigé ; pas d'encours non couvert.",
        "E": "Paiement comptant / à la commande uniquement ; éviter toute exposition à crédit.",
        "NR": "Données insuffisantes : demander les derniers états de synthèse avant toute exposition."}

def classify(s) -> str:
    if pd.isna(s): return "NR"
    for cut, l, _, _ in CLASSES:
        if s >= cut: return l

EDICOM_COLS = ["Raison Sociale", "Dirigeant", "Fonction", "TEL 1", "EMAIL", "WEB", "ICE", "RC", "VILLE RC", "FORM.JUR", "ANNEE CREATION", "CAPITAL",
               "EFFECTIF", "GAME CA", "CA", "ANNEE CA", "FDA", "VOIE", "NUM. VOIE", "COMPLEM. VOIE"]
KEEP = ["CP", "capital", "TA", "RN", "RE", "FR", "BFR", "TN", "CL", "CA_liq", "TRESO_A", "TRESO_P", "CLIENTS", "STOCKS", "AI", "F6_assoc", "F1_fourn",
        "DFIN_LT", "DETTES_TOT", "F4_cnss", "F5_etat", "CPA", "DCT", "NUMERO_ETAT", "actif_ok", "AC", "PC"]

@dataclass
class BuildInputs:
    ompic_cur: str; ompic_prev: str; fy: int; edicom: str

def score_panel(cur: pd.DataFrame, prev: pd.DataFrame, ed: pd.DataFrame, fy: int) -> pd.DataFrame:
    """cur/prev: features.build outputs for FY and FY-1; ed: Edicom frame indexed by Code Firme."""
    o_cur = S.score_year(cur, prev, ed); o_prev = S.score_year(prev, None, ed); o_static = S.score_year(cur, None, ed)
    ci = cur.set_index("F"); pi = prev.set_index("F")
    R = o_cur.copy(); R["score"] = R["score"].round(1)
    R["score_prev"] = o_prev["score"].round(1); R["score_cur_static"] = o_static["score"].round(1)
    R["delta"] = R["score_cur_static"] - R["score_prev"]
    R["perspective"] = np.select([R.delta >= 7, R.delta <= -7], ["En amélioration", "En dégradation"], default="Stable")
    R.loc[R.delta.isna(), "perspective"] = "n.d."
    R["classe"] = R["score"].map(classify)
    R["percentile"] = R["score"].rank(pct=True) * 100; R.loc[~R.scorable, "percentile"] = np.nan
    e = ed.reindex(R.index)
    pts = (30 * pi.reindex(R.index).TA.notna().astype(int) + 20 * ci.reindex(R.index).actif_ok.astype(int) + 20 * e["Raison Sociale"].notna().astype(int)
           + 10 * R["age"].notna().astype(int) + 10 * (R["ca_band"].notna() | (R["effectif"] > 0)).astype(int)
           + 10 * (abs(ci.reindex(R.index).TA_actif - ci.reindex(R.index).TA_passif) < 1).astype(int))
    R["fiabilite_pts"] = pts; R["fiabilite"] = np.select([pts >= 80, pts >= 55], ["Élevée", "Moyenne"], default="Faible")
    for k in KEEP:
        R[k + "_cur"] = ci[k].reindex(R.index); R[k + "_prev"] = pi[k].reindex(R.index)
    for c in EDICOM_COLS:
        R["E_" + c] = ed[c].reindex(R.index) if c in ed.columns else np.nan
    R["edicom_match"] = e["Raison Sociale"].notna()
    R["fy"] = fy; R["pfy"] = fy - 1
    return R

def panel_meta(R: pd.DataFrame, fy: int, quality: list[dict], recent_window: int = 3) -> dict:
    sc = R[R.scorable]
    pos = R[R.edicom_match & (pd.to_numeric(R["E_CA"], errors="coerce") > 0)]
    reconfirm = float((pos.act_code == "ACTIVE").mean()) if len(pos) else float("nan")
    med = {k: float(sc[k].median()) for k in ["headroom", "autonomy", "assoc", "fr_ta", "current", "roa", "re_ta", "tn_ta"]}
    return {"fy": fy, "n_firms": int(len(R)), "n_scorable": int(R.scorable.sum()), "medians": med,
            "class_counts": {k: int(v) for k, v in R.classe.value_counts().items()},
            "status_counts": {k: int(v) for k, v in R.act_code.value_counts().items()},
            "reconfirm_rate": reconfirm, "recent_window": recent_window, "observed_adverse_rate": OBSERVED_ADVERSE_RATE, "backtest": PANEL_BACKTEST_LABEL, "quality": quality,
            "built_at": pd.Timestamp.today().isoformat(timespec="seconds")}

def build_from_frames(ed, a_cur, p_cur, a_prev, p_prev, fy: int, settings: Settings | None = None, today=None, progress=None):
    """Core build. `progress(step_index, label)` is called before each stage (used by the web import)."""
    st = settings or Settings()
    tick = progress or (lambda i, label: None)
    tick(1, "Calcul des indicateurs comptables")
    cur = features.build(a_cur, p_cur, fy); prev = features.build(a_prev, p_prev, fy - 1)
    tick(2, "Calcul des scores")
    R = score_panel(cur, prev, ed, fy)
    tick(3, "Détection de l'activité")
    R = A.add_to(R, today=today, settings=st)
    return R, panel_meta(R, fy, [features.quality_report(prev), features.quality_report(cur)], st.recent_window_years)

def build_scores(inp: BuildInputs, settings: Settings | None = None, today=None) -> tuple[pd.DataFrame, dict]:
    ed = loaders.read_edicom(inp.edicom)
    a, p = loaders.read_ompic(inp.ompic_cur, inp.fy); b, q = loaders.read_ompic(inp.ompic_prev, inp.fy - 1)
    return build_from_frames(ed, a, p, b, q, inp.fy, settings, today)
