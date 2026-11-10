"""Activity-status engine.

Evidence ladder (strongest first):
 1. revenue declared recently (Edicom CA > 0 dated within the recent window)       -> ACTIVE
 2. revenue recorded for the balance-sheet year + operating footprint of the balance sheet -> PROBABLE
 3. dormancy resemblance of the balance sheet (logistic model, CV AUC 0.90)         -> decides INACTIVE / VERIFY
 4. contactability, headcount: shown as evidence only.
The status never feeds the financial-health score. It is an inference, not a legal status.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
from .config import ACTIVITY_MODEL, Settings

_M = json.load(open(ACTIVITY_MODEL, encoding="utf-8"))
P_LOW, P_HIGH = 0.30, 0.60
# share of panel firms with NO recorded revenue, by dormancy-resemblance bin (calibration on the 3,787-firm panel)
DORM_CAL = [(0.10, 0.029), (0.20, 0.142), (0.30, 0.223), (0.45, 0.322), (0.60, 0.576), (0.80, 0.712), (1.01, 0.928)]
PATRIM = ("immobili", "holding", "patrimoin", "fonciere", "foncière", "sci ")
CODES = ("ACTIVE", "PROBABLE", "VERIFY", "INACTIVE")

def cal_rate(p: float) -> float:
    for hi, v in DORM_CAL:
        if p < hi:
            return v
    return DORM_CAL[-1][1]

def _f(x, d=0.0) -> float:
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x):
            return d
    except (TypeError, ValueError):
        pass
    return float(x)

def is_patrimonial(r) -> bool:
    n = str(r.get("E_Raison Sociale") or "").lower() + " "
    return str(r.get("E_FORM.JUR") or "") == "SCI" or any(k in n for k in PATRIM)

def dormancy_features(r) -> dict:
    pos = lambda k: float(abs(_f(r.get(k))) > 0)
    keys = ["TA", "CP", "RN", "AC", "PC"]
    a = [_f(r.get(k + "_cur")) for k in keys]; b = [_f(r.get(k + "_prev")) for k in keys]
    frozen = float(sum(abs(x - y) for x, y in zip(a, b)) < 1 and a[0] > 0)
    return {"clients": pos("CLIENTS_cur"), "fourn": pos("F1_fourn_cur"), "stocks": pos("STOCKS_cur"), "cnss": pos("F4_cnss_cur"),
            "etat": pos("F5_etat_cur"), "immo": pos("AI_cur"), "tiny": float(_f(r.get("TA_cur")) < 50000),
            "rn0": float(abs(_f(r.get("RN_cur"))) < 1), "frozen": frozen,
            "loss2": float(_f(r.get("loss_streak")) >= 2), "roa_neg": float(_f(r.get("roa")) < 0)}

def p_dormant(r) -> float:
    f = dormancy_features(r)
    z = _M["intercept"] + sum(_M["coef"][k] * f[k] for k in _M["features"])
    return float(1 / (1 + np.exp(-z)))

def _ok_tel(t) -> bool:
    if t is None or (isinstance(t, float) and np.isnan(t)):
        return False
    t = str(t)
    return t.strip() != "" and "00 00 00 00" not in t

def status(r, today=None, settings: Settings | None = None) -> dict:
    st = settings or Settings()
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.today()
    fy = int(_f(r.get("fy"), 0)) or None
    recent_from = today.year - st.recent_window_years
    p = p_dormant(r); f = dormancy_features(r)
    ca = pd.to_numeric(r.get("E_CA"), errors="coerce"); cay = pd.to_numeric(r.get("E_ANNEE CA"), errors="coerce")
    has_edi = bool(r.get("edicom_match", False))
    recent = bool(has_edi and pd.notna(ca) and ca > 0 and pd.notna(cay) and cay >= recent_from)
    ca_pos_old = bool(has_edi and pd.notna(ca) and ca > 0 and not recent)
    ca_zero = bool(has_edi and (pd.isna(ca) or ca == 0))
    fy_txt = str(fy) if fy else "dernier exercice"
    ev = []
    if recent: ev.append(("+", f"Chiffre d'affaires {int(cay)} déclaré : {{CA}}"))
    elif ca_pos_old: ev.append(("=", f"Dernier chiffre d'affaires connu : {{CA}} ({int(cay) if pd.notna(cay) else 'année n.d.'}) — aucune donnée plus récente"))
    elif ca_zero: ev.append(("-", f"Aucun chiffre d'affaires enregistré (dernier exercice connu : {fy_txt})"))
    else: ev.append(("=", "Aucun chiffre d'affaires disponible dans la base Edicom"))
    present = [n for n, k in [("clients", "clients"), ("fournisseurs", "fourn"), ("stocks", "stocks"), ("dettes CNSS", "cnss"), ("dettes fiscales", "etat")] if f[k]]
    if len(present) >= 4: ev.append(("+", f"Bilan {fy_txt} à cycle d'exploitation complet : " + ", ".join(present)))
    elif len(present) >= 2: ev.append(("=", f"Bilan {fy_txt} partiellement actif : " + ", ".join(present)))
    else: ev.append(("-", f"Bilan {fy_txt} sans cycle d'exploitation visible (clients, fournisseurs, CNSS, fiscal quasi absents)"))
    if f["rn0"]: ev.append(("-", f"Résultat net {fy_txt} strictement nul"))
    if f["frozen"]: ev.append(("-", f"Bilan {fy_txt} identique à celui de l'exercice précédent (aucun mouvement)"))
    if f["tiny"] and not f["rn0"]: ev.append(("-", f"Total bilan {fy_txt} inférieur à 50 000 DH"))
    eff = pd.to_numeric(r.get("E_EFFECTIF"), errors="coerce")
    if has_edi and pd.notna(eff) and eff > 0: ev.append(("+", f"Effectif déclaré : {int(eff)} salarié(s)"))
    tel = _ok_tel(r.get("E_TEL 1")); mail = pd.notna(r.get("E_EMAIL")); web = pd.notna(r.get("E_WEB"))
    if has_edi:
        if tel and (mail or web): ev.append(("+", "Coordonnées complètes (téléphone + e-mail/site web)"))
        elif tel or mail or web: ev.append(("=", "Coordonnées partielles dans l'annuaire"))
        else: ev.append(("=", "Aucune coordonnée exploitable dans l'annuaire"))
    patr = is_patrimonial(r)
    ta = _f(r.get("TA_cur")); proj = (_f(r.get("AI_cur")) + _f(r.get("STOCKS_cur"))) / max(ta, 1.0)
    substantial = ta >= st.substance_threshold_dh
    if substantial and proj >= 0.5:
        ev.append(("+", f"Bilan substantiel : {ta/1e6:.1f} M DH dont {proj*100:.0f} % d'immobilisations et de stocks".replace(".", ",")))
    last = None
    if recent:
        code, label, conf = "ACTIVE", "Entreprise active", "Élevée"; last = int(cay)
        line = "Activité confirmée par un chiffre d'affaires déclaré en {y}."
    elif ca_pos_old and p < P_LOW:
        code, label, conf = "PROBABLE", "Probablement active", "Moyenne"; last = fy
        line = f"Activité constatée en {fy_txt} (CA et bilan opérationnels), non reconfirmée depuis : à vérifier avant engagement."
    elif ca_pos_old and p < P_HIGH:
        code, label, conf = "VERIFY", "Activité non confirmée", "Faible"; last = fy
        line = f"Un CA a été enregistré ({fy_txt}) mais le bilan est peu opérationnel ; aucune donnée récente."
    elif ca_pos_old:
        code, label, conf = "VERIFY", "Activité non confirmée", "Faible"; last = fy
        line = "CA enregistré mais bilan de type dormant et aucune donnée récente : signaux contradictoires."
    elif (ca_zero or not has_edi) and substantial and p >= P_LOW:
        code, label, conf = "VERIFY", "Activité non confirmée", "Faible"
        line = ("Bilan substantiel composé surtout d'immobilisations et de stocks, sans CA : typique d'un projet en développement (promotion, construction, hôtellerie) ; l'absence de CA ne prouve pas l'inactivité."
                if proj >= 0.5 else "Bilan substantiel sans CA enregistré : l'entreprise n'est pas assimilable à une coquille dormante ; à vérifier.")
    elif ca_zero and patr and p >= P_LOW:
        code, label, conf = "VERIFY", "Activité non confirmée", "Faible"
        line = "Société à vocation patrimoniale/immobilière : l'absence de CA est fréquente sans que la société soit inactive ; à vérifier."
    elif ca_zero and p >= P_HIGH:
        code, label = "INACTIVE", "Probablement inactive"; conf = "Élevée" if p >= 0.80 else "Moyenne"
        line = "Aucun chiffre d'affaires et bilan de type dormant : l'entreprise semble sans activité économique réelle."
    elif ca_zero and p >= P_LOW:
        code, label, conf = "VERIFY", "Activité non confirmée", "Faible"
        line = "Aucun CA enregistré ; le bilan présente des éléments d'exploitation partiels : situation à vérifier."
    elif ca_zero:
        code, label, conf = "VERIFY", "Activité non confirmée", "Faible"; last = fy
        line = f"Aucun CA enregistré mais le bilan {fy_txt} montre une exploitation (le CA peut être non communiqué) : à vérifier."
    else:
        if p >= P_HIGH: code, label, conf = "INACTIVE", "Probablement inactive", "Faible"; line = "Bilan de type dormant ; aucune autre information disponible."
        elif p >= P_LOW: code, label, conf = "VERIFY", "Activité non confirmée", "Faible"; line = "Bilan ambigu ; aucune autre information disponible."
        else: code, label, conf = "PROBABLE", "Probablement active", "Faible"; last = fy; line = f"Bilan {fy_txt} opérationnel ; aucune autre information disponible : à vérifier."
    if code == "INACTIVE" and has_edi and pd.notna(eff) and eff > 0:
        conf = "Moyenne"; line += f" L'effectif déclaré ({int(eff)}) est à confirmer."
    band = "bilan opérationnel" if p < P_LOW else ("bilan ambigu" if p < P_HIGH else "bilan de type dormant")
    return {"code": code, "label": label, "confidence": conf, "last_proof_year": last, "p_dormant": p, "band": band,
            "cal_rate": cal_rate(p), "patrimonial": patr, "line": line.format(y=int(cay) if pd.notna(cay) else ""),
            "evidence": ev, "age_years": (today.year - last) if last else None}

def add_to(df: pd.DataFrame, today=None, settings: Settings | None = None) -> pd.DataFrame:
    out = [status(r, today, settings) for _, r in df.iterrows()]
    df = df.copy()
    df["act_code"] = [o["code"] for o in out]; df["act_label"] = [o["label"] for o in out]; df["act_conf"] = [o["confidence"] for o in out]
    df["act_last"] = [o["last_proof_year"] for o in out]; df["act_p_dorm"] = [o["p_dormant"] for o in out]
    df["act_band"] = [o["band"] for o in out]; df["act_line"] = [o["line"] for o in out]
    return df
