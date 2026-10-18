import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

# Deliberately require a separate, disposable PostgreSQL database.
url = os.environ.get("DG_TEST_DATABASE_URL", "")
if not url or not url.rsplit("/", 1)[-1].startswith("deliveryguard_test"):
    raise RuntimeError(
        "Set DG_TEST_DATABASE_URL to a disposable PostgreSQL deliveryguard_test* database"
    )
os.environ["DG_DATABASE_URL"] = url
os.environ["DG_DEMO"] = "false"
os.environ["DG_API_KEY"] = "test-only-key-32-characters-long-xxxx"

from deliveryguard.api import app  # noqa: E402
from deliveryguard.config import settings  # noqa: E402
from deliveryguard.db import engine  # noqa: E402


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DG_DATA_DIR", str(tmp_path))
    settings.cache_clear()
    command.upgrade(Config(str(Path(__file__).parents[1] / "alembic.ini")), "head")
    with engine().begin() as connection:
        connection.execute(text("TRUNCATE active_model, training_runs, imports, orders CASCADE"))
    yield


@pytest.fixture
def client():
    with TestClient(app) as client:
        client.headers["X-API-Key"] = settings().api_key
        yield client
