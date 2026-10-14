import pytest


@pytest.fixture(autouse=True)
def isolated_operations(tmp_path, monkeypatch):
    """Never poll real feeds or write to the application's DB in offline tests."""
    import api
    monkeypatch.setenv("CRISISLENS_ALERT_POLLING", "0")
    monkeypatch.setenv("CRISISLENS_DB_PATH", str(tmp_path / "operations.sqlite3"))
    monkeypatch.setattr(api, "_operations", None)
