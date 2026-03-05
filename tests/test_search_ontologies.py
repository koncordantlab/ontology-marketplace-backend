"""Tests for search_ontologies combined query optimization."""

from unittest.mock import patch, MagicMock, AsyncMock
from async_helpers import AsyncIteratorFromList
import pytest


@pytest.fixture(autouse=True)
def clear_search_cache():
    """Clear the search cache before each test."""
    from functions.cache import invalidate_search_cache
    invalidate_search_cache()


@pytest.fixture
def mock_driver():
    """Provide a mocked async Neo4j driver."""
    with patch("functions.search_ontologies.get_neo4j_driver") as factory_mock:
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


def _make_record(uuid_val, name, total, is_public=True):
    """Create a mock Neo4j record for search results."""
    node = MagicMock()
    node.__getitem__ = lambda s, k: {
        'uuid': uuid_val, 'name': name, 'source_url': 'http://example.com',
        'description': 'Test', 'is_public': is_public, 'node_count': 5,
        'relationship_count': 10, 'score': None, 'image_url': None,
    }[k]
    node.get = lambda k, d=None: {
        'uuid': uuid_val, 'name': name, 'source_url': 'http://example.com',
        'description': 'Test', 'is_public': is_public, 'node_count': 5,
        'relationship_count': 10, 'score': None, 'image_url': None,
        'created_at': '2025-01-01T00:00:00Z',
    }.get(k, d)

    record = MagicMock()
    record.__getitem__ = lambda s, k: {'o': node, 'tags': ['tag1'], 'total': total}[k]
    return record


async def test_single_query_call(mock_driver):
    """search_ontologies should call session.run exactly once (combined query)."""
    session = mock_driver._session
    records = [_make_record('u1', 'Test Ontology', 1)]
    session.run.return_value = mock_driver._make_result(records)

    from functions.search_ontologies import search_ontologies
    result = await search_ontologies(search_term=None, limit=10, offset=0, request=None)

    assert session.run.call_count == 1
    assert result.success is True
    assert result.data['total'] == 1


async def test_with_search_term(mock_driver):
    """search_ontologies with a search_term includes CONTAINS clause."""
    session = mock_driver._session
    session.run.return_value = mock_driver._make_result([])

    from functions.search_ontologies import search_ontologies
    result = await search_ontologies(search_term="medical", limit=10, offset=0, request=None)

    assert session.run.call_count == 1
    # Verify the query includes search_term parameter
    call_args = session.run.call_args
    params = call_args[0][1]  # second positional arg is params dict
    assert 'search_term' in params


async def test_response_contains_total(mock_driver):
    """Response contains correct total count from combined query."""
    session = mock_driver._session
    records = [
        _make_record('u1', 'Ontology 1', 5),
        _make_record('u2', 'Ontology 2', 5),
    ]
    session.run.return_value = mock_driver._make_result(records)

    from functions.search_ontologies import search_ontologies
    result = await search_ontologies(search_term=None, limit=10, offset=0, request=None)

    assert result.data['total'] == 5
    assert result.data['count'] == 2
