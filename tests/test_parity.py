"""Optional: rebuild from the raw Edicom files and compare to a reference store. Set EDICOM_RAW_DIR to enable."""
import os, pytest
from pathlib import Path

RAW = os.getenv("EDICOM_RAW_DIR")
pytestmark = pytest.mark.skipif(not RAW, reason="set EDICOM_RAW_DIR to the folder with the 4 raw xlsx files")

def test_rebuild_from_raw():
    from edicom_score.pipeline import BuildInputs, build_scores
    d = Path(RAW)
    f = lambda pat: next(d.glob(pat))
    R, meta = build_scores(BuildInputs(f("*OMPIC_2019.xlsx"), f("*OMPIC_2018.xlsx"), 2019, f("*Firmes_Edicom*.xlsx")))
    assert len(R) == 3787 and meta["class_counts"]["A"] == 1141 and meta["status_counts"]["INACTIVE"] == 312
