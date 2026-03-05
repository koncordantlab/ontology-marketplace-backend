"""Shared test fixtures for ontology-marketplace-backend."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app, get_current_user


# ---------------------------------------------------------------------------
# Neo4j driver mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_neo4j_driver():
    """Patch functions.n4j.get_neo4j_driver and return a MagicMock driver.

    The mock wires up driver.session() as a context-manager that yields a
    session mock whose ``run`` returns an empty list by default.  The
    session also supports ``begin_transaction`` returning a transaction
    mock with its own ``run``, ``commit``, and ``rollback``.
    """
    with patch("functions.n4j.get_neo4j_driver") as factory_mock:
        driver = MagicMock(name="neo4j_driver")

        # Transaction mock
        tx = MagicMock(name="neo4j_transaction")
        tx.run.return_value = []

        # Session mock (usable as a context-manager)
        session = MagicMock(name="neo4j_session")
        session.run.return_value = []
        session.begin_transaction.return_value = tx
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)

        driver.session.return_value = session

        factory_mock.return_value = driver
        yield driver


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
