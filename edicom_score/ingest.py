"""Import: detect what is inside the uploaded Excel files and assemble the inputs for a build.

Accepted layouts (any mix, dropped together):
  * the three original files (OMPIC year N, OMPIC year N-1, Edicom firms)
  * ONE workbook with sheets such as  "2018", "2019", "Edicom"   (a year sheet holding Actif + Passif columns)
  * ONE workbook with sheets such as  "Actif 2018", "Passif 2018", "Actif 2019", "Passif 2019", "Edicom"
Sheets are recognised by their columns (ACTIF_*_NET, PASSIF_*_EXACT, 'Raison Sociale'), the year by the sheet or file name.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd
from . import loaders

YEAR_RE = re.compile(r"(?<!\d)(20[0-4]\d)(?!\d)")
ID_RENAME = {"Code firme K": "F", "Code firme": "F", "Code Firme": "F", "Unnamed: 1": "ICE", "Unnamed: 3": "CAPITAL_X"}

@dataclass
class SheetInfo:
    file: str; sheet: str; kind: str            # actif | passif | bilan | edicom | ignored
    year: int | None = None; rows: int = 0; note: str = ""
    def to_dict(self): return self.__dict__.copy()

def _kind(cols: list[str]) -> str:
    c = [str(x).strip() for x in cols]
    has_a = any(x.startswith("ACTIF_") and x.endswith("_NET") for x in c)
    has_p = any(x.startswith("PASSIF_") for x in c)
    if has_a and has_p: return "bilan"
    if has_a: return "actif"
    if has_p: return "passif"
    if "Raison Sociale" in c and "Code Firme" in c: return "edicom"
    return "ignored"

def _year(sheet: str, file: str) -> int | None:
    for s in (sheet, Path(file).stem):
        m = YEAR_RE.findall(s)
        if m: return int(m[-1])
    return None

def scan_file(path) -> list[SheetInfo]:
    """Fast scan: header row + row count of every sheet, without loading the data."""
    from openpyxl import load_workbook
    path = Path(path); out = []
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
            cols = [str(c).strip() for c in first if c is not None]
            k = _kind(cols)
            if k == "ignored":
                out.append(SheetInfo(path.name, ws.title, "ignored", note="feuille non utilisée")); continue
            n = (ws.max_row or 0) - 1
            if n < 1: n = sum(1 for _ in ws.iter_rows(min_row=2, max_col=1, values_only=True))
            out.append(SheetInfo(path.name, ws.title, k, None if k == "edicom" else _year(ws.title, path.name), n))
    finally:
        wb.close()
    return out

def _read_bilan(path, sheet) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in ID_RENAME.items() if k in df.columns and v not in df.columns})
    return df

def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    p_cols = [c for c in df.columns if c.startswith("PASSIF_")]
    a = df[[c for c in df.columns if c not in p_cols]].copy()
    p = df[[c for c in ("F", "NUMERO_ETAT", "ICE") if c in df.columns] + p_cols].copy()
    return a, p

@dataclass
class Plan:
    fy: int | None = None
    sheets: list[SheetInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    edicom_rows: int = 0
    # internal: (kind, year) -> (path, sheet)
    sources: dict = field(default_factory=dict, repr=False)
    @property
    def ready(self) -> bool: return not self.errors and self.fy is not None
    def to_dict(self):
        return {"ready": self.ready, "fy": self.fy, "years": self.years, "files": self.files, "errors": self.errors, "warnings": self.warnings,
                "edicom_rows": self.edicom_rows, "sheets": [s.to_dict() for s in self.sheets]}

def plan(paths: list) -> Plan:
    P = Plan(); P.files = [Path(p).name for p in paths]
    src: dict = {}
    for p in paths:
        try:
            infos = scan_file(p)
        except Exception as e:                      # not an Excel file / corrupted
            P.errors.append(f"« {Path(p).name} » n'a pas pu être lu comme un fichier Excel ({type(e).__name__}).")
            continue
        P.sheets += infos
        for s in infos:
            if s.kind in ("actif", "passif", "bilan", "edicom"):
                if s.kind != "edicom" and s.year is None:
                    P.errors.append(f"Année introuvable pour la feuille « {s.sheet} » ({s.file}) : ajoutez l'année (ex. 2019) dans le nom de la feuille.")
                    continue
                key = (s.kind, s.year)
                if key in src:
                    P.warnings.append(f"Deux feuilles « {s.kind} {s.year or ''} » : « {s.sheet} » ({s.file}) remplace la précédente.")
                src[key] = (str(p), s.sheet, s)
    P.sources = src
    if not any(k[0] == "edicom" for k in src):
        P.errors.append("Aucune feuille Edicom trouvée (colonnes « Code Firme » et « Raison Sociale »).")
    else:
        P.edicom_rows = next(v[2].rows for k, v in src.items() if k[0] == "edicom")
    years = set()
    for y in {k[1] for k in src if k[0] != "edicom"}:
        if (("bilan", y) in src) or (("actif", y) in src and ("passif", y) in src):
            years.add(y)
        else:
            missing = "Passif" if ("actif", y) in src else "Actif"
            P.errors.append(f"Exercice {y} incomplet : la feuille {missing} est absente.")
    P.years = sorted(years)
    cands = [y for y in P.years if y - 1 in years]
    if not cands:
        if not any("incomplet" in e for e in P.errors):
            P.errors.append("Il faut deux exercices consécutifs (par ex. 2018 et 2019) pour calculer le score et sa dynamique.")
    else:
        P.fy = max(cands)
        extra = [y for y in P.years if y not in (P.fy, P.fy - 1)]
        if extra: P.warnings.append(f"Exercices ignorés : {', '.join(map(str, extra))}. Le score utilise {P.fy} et {P.fy - 1}.")
    return P

def load(P: Plan):
    """Return (edicom, actif_cur, passif_cur, actif_prev, passif_prev, fy) ready for the pipeline."""
    if not P.ready: raise ValueError("; ".join(P.errors) or "plan incomplet")
    def year_frames(y):
        if ("bilan", y) in P.sources:
            path, sh, _ = P.sources[("bilan", y)]; return _split(_read_bilan(path, sh))
        a = _read_bilan(*P.sources[("actif", y)][:2]); p = _read_bilan(*P.sources[("passif", y)][:2]); return a, p
    path, sh, _ = next(v for k, v in P.sources.items() if k[0] == "edicom")
    ed = loaders.read_edicom(path, sheet=sh)
    ac, pc = year_frames(P.fy); ap, pp = year_frames(P.fy - 1)
    for name, df in (("Actif", ac), ("Passif", pc), ("Actif", ap), ("Passif", pp)):
        for col in ("F", "NUMERO_ETAT"):
            if col not in df.columns: raise ValueError(f"Colonne « {col} » absente d'une feuille {name}.")
    return ed, ac, pc, ap, pp, P.fy
