"""Tests for Neo4j driver singleton pattern."""

from unittest.mock import patch, MagicMock, AsyncMock
import pytest


def test_get_neo4j_driver_returns_singleton():
    """get_neo4j_driver() called twice returns the same driver object."""
    import functions.n4j as n4j_module
    n4j_module._driver = None  # Reset

    with patch("functions.n4j.AsyncGraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        from functions.n4j import get_neo4j_driver
        d1 = get_neo4j_driver()
        d2 = get_neo4j_driver()

        assert d1 is d2
        mock_gdb.driver.assert_called_once()

    n4j_module._driver = None  # Cleanup


async def test_close_neo4j_driver_resets_singleton():
    """close_neo4j_driver() calls driver.close() and resets the singleton."""
    import functions.n4j as n4j_module
    mock_driver = AsyncMock()
    n4j_module._driver = mock_driver

    from functions.n4j import close_neo4j_driver
    await close_neo4j_driver()

    mock_driver.close.assert_called_once()
    assert n4j_module._driver is None


async def test_close_neo4j_driver_noop_when_no_driver():
    """close_neo4j_driver() is safe to call when no driver exists."""
    import functions.n4j as n4j_module
    n4j_module._driver = None

    from functions.n4j import close_neo4j_driver
    await close_neo4j_driver()  # Should not raise
