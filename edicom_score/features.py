"""Balance-sheet feature engineering (CGNC Actif/Passif) -> one row per firm for one fiscal year."""
from __future__ import annotations
import numpy as np, pandas as pd

def merge_year(actif: pd.DataFrame, passif: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest filing per firm (highest NUMERO_ETAT) and join Actif with Passif."""
    a = actif.sort_values("NUMERO_ETAT").drop_duplicates("F", keep="last")
    p = passif.sort_values("NUMERO_ETAT").drop_duplicates("F", keep="last")
    return a.drop(columns=["ICE"], errors="ignore").merge(p.drop(columns=["ICE"], errors="ignore"), on=["F", "NUMERO_ETAT"], how="inner")

def build(actif: pd.DataFrame, passif: pd.DataFrame, year: int) -> pd.DataFrame:
    m = merge_year(actif, passif)
    g = lambda c: m[c].astype(float)
    A = lambda k: g(f"ACTIF_{k}_NET")
    P = lambda k: g(f"PASSIF_{k}_EXACT")
    d = pd.DataFrame({"F": m.F, "year": year})
    d["actif_ok"] = A("A").notna()
    d["capital"] = P("A2"); d["CP"] = P("A"); d["CPA"] = P("B"); d["DFIN_LT"] = P("C"); d["PROV_D"] = P("D")
    d["DCT"] = P("F"); d["AUTRES_PROV"] = P("G"); d["EC_PC"] = P("H"); d["TRESO_P"] = P("TRESOR")
    d["F1_fourn"] = P("F1"); d["F2_avances"] = P("F2"); d["F3_perso"] = P("F3"); d["F4_cnss"] = P("F4"); d["F5_etat"] = P("F5")
    d["F6_assoc"] = P("F6"); d["F7_autres_cred"] = P("F7")
    d["RN"] = P("A12"); d["RAN"] = P("A10"); d["RES_LEG"] = P("A8"); d["RES_AUT"] = P("A9"); d["RES_INST"] = P("A11")
    d["TA_passif"] = P("A") + P("B") + P("C") + P("D") + P("E") + P("F") + P("G") + P("H") + P("TRESOR")
    # ACTIF_TOT3_NET is the cash-asset subtotal, NOT total assets: rebuild total assets from the components.
    d["TA_actif"] = sum(A(k) for k in "ABCDEFGHI") + A("TOT3")
    d["TA"] = d["TA_actif"].where(d["TA_actif"].notna(), d["TA_passif"])
    d["IMMO_NV"] = A("A"); d["IMMO_INC"] = A("B"); d["IMMO_CORP"] = A("C"); d["IMMO_FIN"] = A("D"); d["EC_A"] = A("E")
    d["AI"] = sum(A(k) for k in "ABCDE")
    d["STOCKS"] = A("F"); d["CREANCES"] = A("G"); d["CLIENTS"] = A("G2"); d["TVP"] = A("H"); d["EC_AC"] = A("I"); d["TRESO_A"] = A("TOT3")
    d["ETAT_ACTIF"] = A("G4"); d["TERRAINS"] = A("C1"); d["PROD_EN_COURS"] = A("F3"); d["MARCHANDISES"] = A("F1")
    d["MAT_FOURN"] = A("F2"); d["PROD_FINIS"] = A("F5")
    d["CAPITAL_FILE"] = g("CAPITAL_X") if "CAPITAL_X" in m else np.nan
    d["NUMERO_ETAT"] = m.NUMERO_ETAT.values
    return derive(d)

def derive(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["FP"] = d.CP + d.CPA + d.DFIN_LT + d.PROV_D                  # permanent financing
    d["FR"] = d.FP - d.AI                                          # working capital (fonds de roulement)
    d["AC"] = d.STOCKS + d.CREANCES + d.TVP + d.EC_AC
    d["PC"] = d.DCT + d.AUTRES_PROV + d.EC_PC
    d["BFR"] = (d.STOCKS + d.CREANCES + d.EC_AC) - d.PC
    d["TN"] = d.TRESO_A - d.TRESO_P
    d["CA_liq"] = d.AC + d.TRESO_A; d["CL"] = d.PC + d.TRESO_P
    d["DETTES_TOT"] = d.TA - d.CP - d.CPA
    d["RE"] = d.RES_LEG + d.RES_AUT + d.RAN + d.RES_INST + d.RN    # retained earnings incl. current result
    return d

def quality_report(d: pd.DataFrame) -> dict:
    ok = d.actif_ok
    return {
        "year": int(d.year.iloc[0]), "rows": int(len(d)), "actif_missing": int((~ok).sum()),
        "identity_FR_BFR_TN": float(((d.FR - d.BFR - d.TN).abs()[ok] < 1).mean()),
        "balance_actif_passif": float(((d.TA_actif - d.TA_passif).abs()[ok] < 1).mean()),
    }
