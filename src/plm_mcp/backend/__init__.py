"""Backend factory and adapter initialization."""

import os
from plm_mcp.backend.base import PLMBackend
from plm_mcp.backend.mock.backend import MockBackend
from plm_mcp.backend.mock.seed_data import seed_mock_data
from plm_mcp.backend.windchill.backend import WindchillBackend
from plm_mcp.config import settings

_backend_instance: PLMBackend | None = None


def get_backend(force_new: bool = False, backend_type: str | None = None) -> PLMBackend:
    """Factory to retrieve the active PLMBackend singleton.

    Controlled dynamically via PLM_BACKEND environment variable ('mock' or 'windchill').
    """
    global _backend_instance

    if _backend_instance is not None and not force_new:
        return _backend_instance

    active_type = (backend_type or os.getenv("PLM_BACKEND") or settings.plm_backend).lower()

    if active_type == "windchill":
        _backend_instance = WindchillBackend()
    else:
        # Default: MockBackend (SQLite)
        db_path = settings.plm_sqlite_path
        backend = MockBackend(db_path=db_path)
        if settings.plm_seed_on_startup:
            seed_mock_data(backend)
        _backend_instance = backend

    return _backend_instance


def reset_backend() -> None:
    """Reset the backend singleton (useful for test isolation)."""
    global _backend_instance
    _backend_instance = None


__all__ = ["PLMBackend", "MockBackend", "WindchillBackend", "get_backend", "reset_backend"]

