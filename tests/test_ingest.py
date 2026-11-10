import pandas as pd, pytest
from edicom_score import ingest

def _book(path, sheets):
    with pd.ExcelWriter(path) as w:
        for name, df in sheets.items(): df.to_excel(w, sheet_name=name, index=False)

ACT = lambda: pd.DataFrame({"Code firme": ["MA1"], "NUMERO_ETAT": [1], "ACTIF_A_NET": [10.0]})
PAS = lambda: pd.DataFrame({"Code firme": ["MA1"], "NUMERO_ETAT": [1], "PASSIF_A_EXACT": [10.0]})
BIL = lambda: pd.DataFrame({"F": ["MA1"], "NUMERO_ETAT": [1], "ACTIF_A_NET": [10.0], "PASSIF_A_EXACT": [10.0]})
EDI = lambda: pd.DataFrame({"Code Firme": ["MA1"], "Raison Sociale": ["Alpha"], "ICE": [1]})

def test_single_workbook_three_sheets(tmp_path):
    p = tmp_path / "all.xlsx"; _book(p, {"2018": BIL(), "2019": BIL(), "Edicom": EDI()})
    P = ingest.plan([p])
    assert P.ready and P.fy == 2019 and P.years == [2018, 2019] and P.edicom_rows == 1
    assert {s.kind for s in P.sheets} == {"bilan", "edicom"}

def test_separate_actif_passif_sheets_and_files(tmp_path):
    a, b, c = tmp_path / "OMPIC_2019.xlsx", tmp_path / "OMPIC_2018.xlsx", tmp_path / "firmes.xlsx"
    _book(a, {"Actif 2019": ACT(), "Passif 2019": PAS()}); _book(b, {"Actif 2018": ACT(), "Passif 2018": PAS(), "correspondance": pd.DataFrame({"x": [1]})}); _book(c, {"Firmes": EDI()})
    P = ingest.plan([a, b, c])
    assert P.ready and P.fy == 2019
    assert any(s.kind == "ignored" for s in P.sheets)

def test_year_taken_from_file_name_when_sheet_has_none(tmp_path):
    a, b, c = tmp_path / "bilans_2019.xlsx", tmp_path / "bilans_2018.xlsx", tmp_path / "e.xlsx"
    _book(a, {"Actif": ACT(), "Passif": PAS()}); _book(b, {"Actif": ACT(), "Passif": PAS()}); _book(c, {"Edicom": EDI()})
    assert ingest.plan([a, b, c]).fy == 2019

def test_latest_consecutive_pair_is_used(tmp_path):
    p = tmp_path / "x.xlsx"; _book(p, {"2018": BIL(), "2022": BIL(), "2023": BIL(), "Edicom": EDI()})
    P = ingest.plan([p]); assert P.fy == 2023 and any("ignorés" in w for w in P.warnings)

@pytest.mark.parametrize("sheets,fragment", [
    ({"2019": BIL(), "Edicom": EDI()}, "deux exercices"),
    ({"2018": BIL(), "2019": BIL()}, "Edicom"),
    ({"Actif 2019": ACT(), "Passif 2019": PAS(), "Actif 2018": ACT(), "Edicom": EDI()}, "incomplet"),
])
def test_helpful_errors(tmp_path, sheets, fragment):
    p = tmp_path / "x.xlsx"; _book(p, sheets); P = ingest.plan([p])
    assert not P.ready and any(fragment.lower() in e.lower() for e in P.errors)

def test_not_an_excel_file(tmp_path):
    p = tmp_path / "notes.xlsx"; p.write_text("hello")
    P = ingest.plan([p]); assert not P.ready and "Excel" in P.errors[0]
