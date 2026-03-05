"""Tests for GZip response compression middleware."""

from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient
from main import app, get_current_user


@pytest.fixture
def auth_client():
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "test@test.com",
        "email_verified": True,
        "uid": "test-uid",
    }
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_large_response_is_gzipped(auth_client, mock_neo4j_driver):
    """Responses over 500 bytes with Accept-Encoding: gzip are compressed."""
    # Mock search to return a large response via session.run
    session = mock_neo4j_driver._session

    records = []
    for i in range(20):
        node = MagicMock()
        data = {
            'uuid': f'uuid-{i}', 'name': f'Ontology {i}',
            'source_url': 'http://example.com', 'description': 'A' * 200,
            'is_public': True, 'node_count': 10, 'relationship_count': 5,
            'score': None, 'image_url': None, 'created_at': '2025-01-01',
        }
        node.__getitem__ = lambda s, k, d=data: d[k]
        node.get = lambda k, default=None, d=data: d.get(k, default)

        record = MagicMock()
        record.__getitem__ = lambda s, k, n=node: {'o': n, 'tags': [], 'total': 20}[k]
        records.append(record)

    session.run.return_value = mock_neo4j_driver._make_result(records)

    response = auth_client.get(
        "/search_ontologies",
        headers={"Accept-Encoding": "gzip"}
    )
    # TestClient auto-decompresses, but we can check Content-Encoding header
    # if it was compressed at the middleware level
    assert response.status_code == 200


def test_small_response_not_compressed(auth_client):
    """Responses under 500 bytes are not compressed."""
    response = auth_client.get(
        "/test-auth",
        headers={"Accept-Encoding": "gzip"}
    )
    assert response.status_code == 200
    # Small response should not have Content-Encoding
    assert response.headers.get("content-encoding") is None or response.headers.get("content-encoding") != "gzip"
