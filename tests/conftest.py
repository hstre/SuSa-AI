import pytest

from susa import db
from susa.config import Config


@pytest.fixture
def env(tmp_path):
    cfg = Config.load(tmp_path)
    cfg.data["embed"]["backend"] = "test-hash"
    conn = db.connect(cfg.db_path)
    yield cfg, conn
    conn.close()
