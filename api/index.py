"""Vercel entry point: exposes the FastAPI app (API + web interface) as a serverless function."""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("EDICOM_STORE_DIR", str(ROOT / "store"))     # scores prepared with `python -m edicom_score vercel`
os.environ.setdefault("EDICOM_READONLY", "1")                      # serverless disk is read-only
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")            # matplotlib needs a writable cache dir

from edicom_score.api import create_app  # noqa: E402

app = create_app()
