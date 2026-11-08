"""Pytest configuration and test fixtures."""

import os
import pytest
from plm_mcp.backend import get_backend, reset_backend
from plm_mcp.backend.mock.backend import MockBackend
from plm_mcp.backend.mock.seed_data import seed_mock_data


@pytest.fixture(autouse=True)
def setup_test_backend(monkeypatch):
    """Fixture providing a fresh in-memory SQLite backend for every test function."""
    monkeypatch.setenv("PLM_BACKEND", "mock")
    monkeypatch.setenv("PLM_SQLITE_PATH", ":memory:")
    monkeypatch.setenv("PLM_SEED_ON_STARTUP", "false")

    # Reset any previous singleton
    reset_backend()

    # Create fresh in-memory backend
    test_backend = MockBackend(db_path=":memory:")
    # Seed standard test dataset
    seed_mock_data(test_backend)

    # Monkeypatch get_backend to always return this test backend
    monkeypatch.setattr("plm_mcp.backend.get_backend", lambda *args, **kwargs: test_backend)
    monkeypatch.setattr("plm_mcp.tools.parts.get_backend", lambda *args, **kwargs: test_backend)
    monkeypatch.setattr("plm_mcp.tools.bom.get_backend", lambda *args, **kwargs: test_backend)
    monkeypatch.setattr("plm_mcp.tools.documents.get_backend", lambda *args, **kwargs: test_backend)
    monkeypatch.setattr("plm_mcp.tools.changes.get_backend", lambda *args, **kwargs: test_backend)
    monkeypatch.setattr("plm_mcp.tools.suppliers.get_backend", lambda *args, **kwargs: test_backend)

    yield test_backend

    reset_backend()

