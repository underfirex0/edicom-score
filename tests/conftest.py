import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edicom_score.config import Settings
from edicom_score.service import ScoreService

MINI = Path(__file__).parent / "data" / "mini_store"

@pytest.fixture(scope="session")
def svc(tmp_path_factory):
    s = Settings(store_dir=MINI, pdf_cache_dir=tmp_path_factory.mktemp("cache"))
    return ScoreService(s)
