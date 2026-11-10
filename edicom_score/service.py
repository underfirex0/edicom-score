"""High-level service: lookup + PDF generation with a disk cache keyed on the panel build."""
from __future__ import annotations
import hashlib, threading
from pathlib import Path
from .config import Settings, get_settings
from .store import Store, summary_row
from .report import render_report, safe_name

class ScoreService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.store = Store(self.settings.store_dir)
        self.cache = Path(self.settings.pdf_cache_dir)
        try: self.cache.mkdir(parents=True, exist_ok=True)
        except OSError: pass                      # caching is an optimisation: never block PDF generation on it
        self._stamp = self._make_stamp()
        self._lock = threading.Lock()          # matplotlib is not thread-safe: one render at a time

    def _make_stamp(self):
        return hashlib.md5(str(self.store.meta.get("built_at", "")).encode()).hexdigest()[:8]

    def pdf(self, code: str) -> tuple[bytes, str]:
        r = self.store.get(code)
        if r is None: raise KeyError(code)
        fn = f"{safe_name(str(r['E_Raison Sociale']))}_{code}.pdf"
        # cache entry is valid for one panel build and one calendar day (the report carries the issue date)
        from datetime import date
        p = self.cache / f"{code}_{self._stamp}_{date.today():%Y%m%d}.pdf"
        try:
            if p.exists(): return p.read_bytes(), fn
        except OSError: pass
        with self._lock:
            b = render_report(r, self.store.meta)
        try: p.write_bytes(b)
        except OSError: pass                      # read-only or full disk: serve the PDF anyway
        return b, fn

    def status(self, code: str) -> dict | None:
        r = self.store.get(code)
        return summary_row(r) if r is not None else None
