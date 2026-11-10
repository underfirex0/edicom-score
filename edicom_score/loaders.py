"""Read the raw workbooks (OMPIC Actif/Passif per year, Edicom firm file, field dictionary) into clean frames."""
from __future__ import annotations
import pandas as pd

def _sheet(xl: pd.ExcelFile, prefix: str) -> str:
    for n in xl.sheet_names:
        if n.lower().startswith(prefix.lower()):
            return n
    raise ValueError(f"No sheet starting with '{prefix}' in {xl.sheet_names}")

def read_ompic(path, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (actif, passif) with firm code in column 'F'. Handles the 2019 layout where ICE and capital sit in unnamed columns."""
    xl = pd.ExcelFile(path)
    a = xl.parse(_sheet(xl, "Actif"))
    p = xl.parse(_sheet(xl, "Passif"))
    a = a.rename(columns={"Code firme K": "F", "Code firme": "F", "Unnamed: 1": "ICE", "Unnamed: 3": "CAPITAL_X"})
    p = p.rename(columns={"Code firme K": "F", "Code firme": "F"})
    for df, name in ((a, "Actif"), (p, "Passif")):
        for col in ("F", "NUMERO_ETAT"):
            if col not in df.columns:
                raise ValueError(f"{name} {year}: missing column {col}")
    return a, p

def read_edicom(path, sheet=None) -> pd.DataFrame:
    """Edicom firm file indexed by 'Code Firme'; column names are stripped (the source has trailing blanks)."""
    xl = pd.ExcelFile(path)
    df = xl.parse(sheet if sheet is not None else xl.sheet_names[0])
    df.columns = [str(c).strip() for c in df.columns]
    if "Code Firme" not in df.columns:
        raise ValueError("Edicom file must contain a 'Code Firme' column")
    df = df.drop_duplicates("Code Firme", keep="last").set_index("Code Firme")
    ice = pd.to_numeric(df["ICE"], errors="coerce")
    df["ICE"] = ice.map(lambda v: str(int(v)).zfill(15) if pd.notna(v) else None)
    return df

def read_dictionary(path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = df.iloc[:, :2]
    df.columns = ["Code", "Libelle"]
    return df
