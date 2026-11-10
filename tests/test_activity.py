import pandas as pd
from edicom_score import activity as A

def firm(**kw):
    base = dict(fy=2019, edicom_match=True, TA_cur=300000, TA_prev=280000, CP_cur=100000, CP_prev=90000, RN_cur=5000, RN_prev=4000,
                AC_cur=250000, AC_prev=240000, PC_cur=200000, PC_prev=190000, CLIENTS_cur=100000, F1_fourn_cur=80000, STOCKS_cur=20000,
                F4_cnss_cur=3000, F5_etat_cur=4000, AI_cur=50000, loss_streak=0, roa=0.02, **{"E_Raison Sociale": "Alpha Trading", "E_FORM.JUR": "SARL"})
    base.update(kw); return pd.Series(base)

TODAY = "2026-11-10"

def test_recent_revenue_means_active():
    st = A.status(firm(**{"E_CA": 2_000_000, "E_ANNEE CA": 2024}), today=TODAY)
    assert st["code"] == "ACTIVE" and st["last_proof_year"] == 2024

def test_old_revenue_is_probable():
    st = A.status(firm(**{"E_CA": 2_000_000, "E_ANNEE CA": 2019}), today=TODAY)
    assert st["code"] in {"PROBABLE", "VERIFY"}

def test_dormant_shell_is_inactive():
    r = firm(**{"E_CA": 0, "E_ANNEE CA": 2019}, TA_cur=12000, TA_prev=12000, CP_cur=-3000, CP_prev=-3000, RN_cur=0, RN_prev=0, AC_cur=12000, AC_prev=12000,
             PC_cur=15000, PC_prev=15000, CLIENTS_cur=0, F1_fourn_cur=0, STOCKS_cur=0, F4_cnss_cur=0, F5_etat_cur=0, AI_cur=0, loss_streak=2, roa=-0.1)
    st = A.status(r, today=TODAY)
    assert st["code"] == "INACTIVE" and st["p_dormant"] > 0.6

def test_substance_rule_prevents_inactive_label():
    # big balance sheet, no revenue (project stage) must never be labelled inactive
    r = firm(**{"E_CA": 0, "E_ANNEE CA": 2019}, TA_cur=5_000_000, TA_prev=5_000_000, CLIENTS_cur=0, F1_fourn_cur=0, F4_cnss_cur=0, F5_etat_cur=0, RN_cur=0, RN_prev=0)
    assert A.status(r, today=TODAY)["code"] != "INACTIVE"

def test_patrimonial_name_rule():
    r = firm(**{"E_CA": 0, "E_ANNEE CA": 2019, "E_Raison Sociale": "Immobiliere Atlas"}, CLIENTS_cur=0, F1_fourn_cur=0, RN_cur=0, RN_prev=0, TA_cur=400000, TA_prev=400000)
    assert A.is_patrimonial(r)
    assert A.status(r, today=TODAY)["code"] != "INACTIVE"

def test_recent_window_is_relative_to_today():
    r = firm(**{"E_CA": 1_000_000, "E_ANNEE CA": 2024})
    assert A.status(r, today="2026-11-10")["code"] == "ACTIVE"
    assert A.status(r, today="2031-01-01")["code"] != "ACTIVE"   # 2024 is no longer recent in 2031

def test_probabilities_bounded():
    assert 0 <= A.p_dormant(firm()) <= 1
