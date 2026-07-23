import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path) -> TestClient:
    db_path = tmp_path / "test.db"
    os.environ["LIGHTCODE_DATABASE_PATH"] = str(db_path)

    with TestClient(app) as c:
        yield c

    os.environ.pop("LIGHTCODE_DATABASE_PATH", None)
