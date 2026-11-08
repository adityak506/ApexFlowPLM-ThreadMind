"""Tests for WindchillBackend adapter stub and interface adherence."""

import pytest
from plm_mcp.backend.base import PLMBackend
from plm_mcp.backend.windchill.backend import WindchillBackend


def test_windchill_backend_implements_interface():
    backend = WindchillBackend()
    assert isinstance(backend, PLMBackend)


def test_windchill_backend_methods_raise_not_implemented():
    backend = WindchillBackend()
    with pytest.raises(NotImplementedError, match="verify against Windchill docs"):
        backend.get_part("DRN-1000")

    with pytest.raises(NotImplementedError, match="verify against Windchill docs"):
        backend.search_parts("drone")

