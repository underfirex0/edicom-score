"""Runtime settings. Everything can be overridden with environment variables (EDICOM_*)."""
from __future__ import annotations
import os, tempfile
from dataclasses import dataclass, field
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
FONT_DIR = PKG_DIR / "fonts"
ACTIVITY_MODEL = PKG_DIR / "activity_model.json"

# Back-test 2018 -> 2019 (3,787 firms): share of firms in an adverse state one year after being in each class.
# These describe the calibration panel; re-measure them when a new back-test is run.
OBSERVED_ADVERSE_RATE = {"A": 0.028, "B": 0.041, "C": 0.142, "D": 0.457, "E": 0.920}
PANEL_BACKTEST_LABEL = "2018→2019"

@dataclass
class Settings:
    store_dir: Path = field(default_factory=lambda: Path(os.getenv("EDICOM_STORE_DIR", "output")))
    pdf_cache_dir: Path | None = None
    api_key: str | None = field(default_factory=lambda: os.getenv("EDICOM_API_KEY") or None)
    recent_window_years: int = int(os.getenv("EDICOM_RECENT_WINDOW", "3"))   # revenue newer than this counts as "recent proof of activity"
    substance_threshold_dh: float = float(os.getenv("EDICOM_SUBSTANCE_DH", "1000000"))
    # Hosting mode. On Vercel (or EDICOM_READONLY=1) the disk is read-only: no import, no background jobs, PDFs cached in /tmp.
    read_only: bool = field(default_factory=lambda: bool(os.getenv("EDICOM_READONLY") or os.getenv("VERCEL")))
    require_key: bool = field(default_factory=lambda: bool(os.getenv("VERCEL") or os.getenv("EDICOM_REQUIRE_KEY")))   # public hosting: refuse to serve data without a key
    batch_max: int | None = None
    zip_max_bytes: int = int(os.getenv("EDICOM_ZIP_MAX_BYTES", str(4_200_000)))   # Vercel caps a response at 4.5 MB

    def __post_init__(self):
        self.store_dir = Path(self.store_dir)
        if self.pdf_cache_dir is None:
            env = os.getenv("EDICOM_PDF_CACHE")
            self.pdf_cache_dir = Path(env) if env else (Path(tempfile.gettempdir()) / "edicom_pdf_cache" if self.read_only else self.store_dir / "pdf_cache")
        if self.batch_max is None:
            self.batch_max = int(os.getenv("EDICOM_BATCH_MAX", "12" if self.read_only else "1000"))
        self.pdf_cache_dir = Path(self.pdf_cache_dir)

def get_settings() -> Settings:
    return Settings()
