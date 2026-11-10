"""Vercel entry point: exposes the FastAPI app (API + web interface) as a serverless function."""
import os, sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("EDICOM_STORE_DIR", str(ROOT / "store"))     # scores prepared with `python -m edicom_score vercel`
os.environ.setdefault("EDICOM_READONLY", "1")                      # serverless disk is read-only
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")            # matplotlib needs a writable cache dir

from edicom_score.api import create_app  # noqa: E402

_PREFIX = "/api/index"


class RestorePath:
    """Vercel hands a rewritten request to the function with the *function's* path (/api/index), not the
    path the browser asked for. vercel.json passes the real path in the `__p` query parameter; we put it back
    before FastAPI routes the request. A request that already carries its real path is left untouched."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            pairs = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
            real = next((v for k, v in pairs if k == "__p"), None)
            path = scope.get("path", "/")
            if real is not None:
                path = "/" + real.lstrip("/")
            elif path == _PREFIX or path.startswith(_PREFIX + "/"):
                path = path[len(_PREFIX):] or "/"
            if path != scope.get("path"):
                drop = {"__p", "path"} if real is not None else {"__p"}      # Vercel also adds a stray `path` parameter
                rest = urlencode([(k, v) for k, v in pairs if k not in drop])
                scope = dict(scope, path=path, raw_path=path.encode("utf-8"), query_string=rest.encode("latin-1"))
        await self.inner(scope, receive, send)


app = RestorePath(create_app())
