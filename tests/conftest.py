"""Shared test fixtures for ontology-marketplace-backend."""

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from main import app, get_current_user
from async_helpers import AsyncIteratorFromList


# ---------------------------------------------------------------------------
# Neo4j driver mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_neo4j_driver():
    """Patch functions.n4j.get_neo4j_driver and return async-compatible mocks.

    The mock wires up driver.session() as an async context manager that yields
    a session mock whose ``run`` returns an AsyncMock result supporting
    async iteration and await .single().
    """
    with patch("functions.n4j.get_neo4j_driver") as factory_mock:
        import functions.n4j
        functions.n4j._driver = None

        driver = MagicMock(name="neo4j_driver")

        # Create an async-compatible result mock
        def make_result(data=None):
            if data is None:
                data = []
            result = AsyncMock(name="neo4j_result")
            result.single = AsyncMock(return_value=None)
            # Support async for using proper async iterator
            result.__aiter__ = lambda self=None, d=data: AsyncIteratorFromList(d)
            return result

        # Session mock (usable as async context manager)
        session = AsyncMock(name="neo4j_session")
        session.run = AsyncMock(return_value=make_result())
        session.begin_transaction = MagicMock()

        # Transaction mock
        tx = AsyncMock(name="neo4j_transaction")
        tx.run = AsyncMock(return_value=make_result())
        session.begin_transaction.return_value = tx

        # Make session usable as `async with driver.session() as session:`
        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)
        driver.session = MagicMock(return_value=session_ctx)

        # Also support `async with driver:` pattern
        driver.__aenter__ = AsyncMock(return_value=driver)
        driver.__aexit__ = AsyncMock(return_value=False)

        factory_mock.return_value = driver

        # Attach helpers to driver for easy test setup
        driver._session = session
        driver._make_result = make_result

        yield driver

        functions.n4j._driver = None


# ---------------------------------------------------------------------------
# User identity dicts
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_current_user():
    """Regular authenticated user identity."""
    return {
        "email": "testuser@example.com",
        "email_verified": True,
        "uid": "test-uid-123",
    }


@pytest.fixture
def mock_admin_user():
    """Admin authenticated user identity."""
    return {
        "email": "admin@example.com",
        "email_verified": True,
        "uid": "admin-uid-456",
        "is_admin": True,
    }


# ---------------------------------------------------------------------------
# FastAPI TestClients
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client(mock_current_user):
    """TestClient whose requests are authenticated as a regular user."""
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def test_client_admin(mock_admin_user):
    """TestClient whose requests are authenticated as an admin user."""
    app.dependency_overrides[get_current_user] = lambda: mock_admin_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def test_client_unauth():
    """TestClient with NO auth override — requests will be unauthenticated."""
    # Ensure no leftover override
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        yield client
