"""Excel export of the whole scored panel (for analysts / bulk review)."""
from __future__ import annotations
import numpy as np, pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from .pipeline import CLASS_LABEL

FN = "Arial"
CLS_COL = {"A": "1E9E5A", "B": "7CB518", "C": "F2A900", "D": "E8590C", "E": "C92A2A", "NR": "9CA3AF"}
ACT_COL = {"ACTIVE": "1E9E5A", "PROBABLE": "13A89E", "VERIFY": "F2A900", "INACTIVE": "C92A2A"}

def _cols(R: pd.DataFrame, fy: int):
    lab = R.classe.map(lambda c: CLASS_LABEL[c][0]); risk = R.classe.map(lambda c: CLASS_LABEL[c][1])
    return [
        ("Code firme", R.index), ("Raison sociale", R["E_Raison Sociale"]), ("ICE", R["E_ICE"]), ("Ville RC", R["E_VILLE RC"]),
        ("Forme jur.", R["E_FORM.JUR"]), ("Année création", R["E_ANNEE CREATION"]),
        ("Statut d'activité", R["act_label"]), ("Fiabilité du statut", R["act_conf"]), ("Dernière preuve d'activité", R["act_last"]),
        ("Ressemblance à une société dormante (%)", (R["act_p_dorm"] * 100).round(0)), ("Motif du statut", R["act_line"]),
        (f"Score {fy} (0-100)", R["score"]), ("Classe", R["classe"]), ("Libellé", lab), ("Niveau de risque", risk),
        ("Percentile (panel)", R["percentile"].round(0)),
        ("P1 Solvabilité", R["P1"].round(1)), ("P2 Liquidité", R["P2"].round(1)), ("P3 Rentabilité", R["P3"].round(1)),
        ("P4 Dynamique", R["P4"].round(1)), ("P5 Profil Edicom", R["P5"].round(1)),
        ("Perspective", R["perspective"]), ("Fiabilité des données", R["fiabilite"]),
        (f"Total bilan {fy} (DH)", R["TA_cur"].round(0)), (f"Capitaux propres {fy} (DH)", R["CP_cur"].round(0)),
        (f"Résultat net {fy} (DH)", R["RN_cur"].round(0)),
        ("Effectif Edicom", R["E_EFFECTIF"]), ("CA Edicom (DH)", R["E_CA"]), ("Année CA Edicom", R["E_ANNEE CA"]),
        ("Correspondance Edicom", R["edicom_match"].map({True: "Oui", False: "Non"})),
    ]

def export_xlsx(R: pd.DataFrame, meta: dict, path) -> None:
    fy = int(meta.get("fy", 0))
    cols = _cols(R, fy)
    df = pd.DataFrame({n: v for n, v in cols}).reset_index(drop=True)
    df = df.sort_values(df.columns[11], ascending=False, na_position="last")
    wb = Workbook(); ws = wb.active; ws.title = f"Scores {fy}"
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and not np.isfinite(v)) else v for v in row])
    hdr = PatternFill("solid", fgColor="0B2545")
    for c in ws[1]:
        c.font = Font(name=FN, bold=True, color="FFFFFF", size=10); c.fill = hdr
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[1].height = 42; ws.freeze_panes = "C2"; ws.auto_filter.ref = ws.dimensions
    names = list(df.columns); ci = names.index("Classe") + 1; si = names.index("Statut d'activité") + 1
    code2col = {"Entreprise active": "1E9E5A", "Probablement active": "13A89E", "Activité non confirmée": "F2A900", "Probablement inactive": "C92A2A"}
    wide = {"Raison sociale": 34, "Motif du statut": 70, "ICE": 17, "Statut d'activité": 22}
    for j, n in enumerate(names, 1):
        ws.column_dimensions[get_column_letter(j)].width = wide.get(n, 15)
        for i in range(2, ws.max_row + 1):
            c = ws.cell(i, j); c.font = Font(name=FN, size=9)
            if "(DH)" in n: c.number_format = "#,##0;-#,##0"
    for i in range(2, ws.max_row + 1):
        c = ws.cell(i, ci)
        if c.value in CLS_COL:
            c.fill = PatternFill("solid", fgColor=CLS_COL[c.value]); c.font = Font(name=FN, size=9, bold=True, color="FFFFFF"); c.alignment = Alignment(horizontal="center")
        c = ws.cell(i, si)
        if c.value in code2col:
            c.fill = PatternFill("solid", fgColor=code2col[c.value]); c.font = Font(name=FN, size=9, bold=True, color="FFFFFF")
    lg = wb.create_sheet("Légende")
    bt = meta.get("backtest", "")
    rows = [(f"EDICOM SCORE ENTREPRISE — exercice {fy} + statut d'activité", ""), ("", ""),
            ("Classe", "Seuil · niveau de risque · taux de situations défavorables observé (test rétrospectif sur le panel)"),
            ("A", "≥ 75 · Très solide"), ("B", "60-75 · Solide"), ("C", "45-60 · Vigilance"), ("D", "30-45 · Fragile"), ("E", "< 30 · Détresse"),
            ("NR", "Non noté : total bilan < 10 000 DH ou bilan manquant"), ("", ""),
            ("Piliers", "P1 Solvabilité 30 % · P2 Liquidité 10 % · P3 Rentabilité 28 % · P4 Dynamique 10 % · P5 Profil Edicom 22 %"),
            ("Plafonds", "CP < ¼ du capital (art. 357 loi 17-95 / art. 86 loi 5-96) → score ≤ 45 ; CP négatifs → ≤ 30"),
            ("Statut d'activité", "Inférence, évaluée séparément du score. Entreprise active = CA récent déclaré ; Probablement active ; Activité non confirmée ; Probablement inactive."),
            ("Limite", "Ne remplace pas la vérification au registre du commerce (OMPIC), à l'ICE (ice.gov.ma) ni les attestations DGI/CNSS."),
            ("Test rétrospectif", str(bt))]
    for r in rows: lg.append(list(r))
    lg.column_dimensions["A"].width = 28; lg.column_dimensions["B"].width = 130
    for r in lg.iter_rows():
        for c in r: c.font = Font(name=FN, size=10); c.alignment = Alignment(wrap_text=True, vertical="top")
    lg["A1"].font = Font(name=FN, size=12, bold=True, color="0B2545")
    wb.save(path)
