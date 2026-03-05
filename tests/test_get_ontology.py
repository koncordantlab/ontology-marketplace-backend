"""Tests for GET /ontologies/{id} endpoint."""

from unittest.mock import patch, MagicMock, AsyncMock
from async_helpers import AsyncIteratorFromList
import pytest
from fastapi.testclient import TestClient
from main import app, get_current_user


@pytest.fixture
def mock_driver():
    with patch("functions.get_ontology.get_neo4j_driver") as factory_mock:
        driver = MagicMock(name="neo4j_driver")

        def make_result(data=None):
            if data is None:
                data = []
            result = AsyncMock(name="neo4j_result")
            result.single = AsyncMock(return_value=None)
            result.__aiter__ = lambda self=None, d=data: AsyncIteratorFromList(d)
            return result

        session = AsyncMock(name="neo4j_session")
        session.run = AsyncMock(return_value=make_result())

        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)
        driver.session = MagicMock(return_value=session_ctx)

        factory_mock.return_value = driver

        driver._session = session
        driver._make_result = make_result

        yield driver


@pytest.fixture
def auth_client():
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "test@test.com", "email_verified": True, "uid": "test-uid",
    }
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def unauth_client():
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        yield client


def _make_node(uuid_val='ont-1', name='Test Ontology', is_public=True):
    node = MagicMock()
    data = {
        'uuid': uuid_val, 'name': name, 'source_url': 'http://example.com',
        'description': 'Test description', 'is_public': is_public,
        'node_count': 5, 'relationship_count': 10, 'score': None,
        'image_url': None, 'created_at': '2025-01-01T00:00:00Z',
    }
    node.__getitem__ = lambda s, k: data[k]
    node.get = lambda k, d=None: data.get(k, d)
    return node


def _make_record(node, tags):
    """Create a mock Neo4j record for get_ontology results."""
    record = MagicMock()
    record.__getitem__ = lambda s, k: {'o': node, 'tags': tags}[k]
    return record


async def test_get_ontology_returns_single(mock_driver):
    """get_ontology_by_id returns a single ontology with tags."""
    session = mock_driver._session
    node = _make_node()
    records = [_make_record(node, ['medical', 'research'])]
    session.run.return_value = mock_driver._make_result(records)

    from functions.get_ontology import get_ontology_by_id
    result = await get_ontology_by_id('ont-1', fuid='user-1')

    assert result.success is True
    assert result.data['uuid'] == 'ont-1'
    assert result.data['tags'] == ['medical', 'research']


async def test_get_ontology_not_found(mock_driver):
    """get_ontology_by_id returns 404 when not found."""
    session = mock_driver._session
    session.run.return_value = mock_driver._make_result([])

    from functions.get_ontology import get_ontology_by_id
    result = await get_ontology_by_id('nonexistent', fuid='user-1')

    assert result.success is False
    assert 'not found' in result.message.lower()


async def test_get_ontology_public_no_auth(mock_driver):
    """Public ontology accessible without auth."""
    session = mock_driver._session
    node = _make_node(is_public=True)
    records = [_make_record(node, [])]
    session.run.return_value = mock_driver._make_result(records)

    from functions.get_ontology import get_ontology_by_id
    result = await get_ontology_by_id('ont-1', fuid=None)

    assert result.success is True
    # Verify query doesn't include fuid parameter
    call_args = session.run.call_args
    params = call_args[0][1]  # second positional arg is params dict
    assert 'fuid' not in params
