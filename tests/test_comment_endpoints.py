import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from async_helpers import AsyncIteratorFromList


def _make_async_session():
    """Create an async-compatible session mock with driver."""
    def make_result(data=None):
        if data is None:
            data = []
        result = AsyncMock(name="neo4j_result")
        result.single = AsyncMock(return_value=None)
        result.__aiter__ = lambda self=None, d=data: AsyncIteratorFromList(d)
        return result

    driver = MagicMock()
    session = AsyncMock(name="neo4j_session")
    session.run = AsyncMock(return_value=make_result())

    session_ctx = AsyncMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=False)
    driver.session = MagicMock(return_value=session_ctx)

    return driver, session, make_result


class TestCommentEndpoints:
    def test_create_comment_201(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver, session, make_result = _make_async_session()
            mock_get.return_value = driver

            # Mock ontology accessible
            ont_record = MagicMock()
            ont_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
            rate_record = MagicMock()
            rate_record.__getitem__ = lambda self, k: {"recent_count": 0}[k]

            ont_result = make_result()
            ont_result.single = AsyncMock(return_value=ont_record)
            rate_result = make_result()
            rate_result.single = AsyncMock(return_value=rate_record)
            create_result = make_result()

            session.run.side_effect = [ont_result, rate_result, create_result]

            response = test_client.post(
                "/ontologies/ont-1/comments",
                json={"content": "Great ontology!"}
            )
            assert response.status_code == 201
            assert response.json()["success"] is True

    def test_create_comment_rate_limit_429(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver, session, make_result = _make_async_session()
            mock_get.return_value = driver

            ont_record = MagicMock()
            ont_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
            rate_record = MagicMock()
            rate_record.__getitem__ = lambda self, k: {"recent_count": 6}[k]

            ont_result = make_result()
            ont_result.single = AsyncMock(return_value=ont_record)
            rate_result = make_result()
            rate_result.single = AsyncMock(return_value=rate_record)

            session.run.side_effect = [ont_result, rate_result]

            response = test_client.post(
                "/ontologies/ont-1/comments",
                json={"content": "Too many comments"}
            )
            assert response.status_code == 429

    def test_get_comments(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver, session, make_result = _make_async_session()
            mock_get.return_value = driver

            from datetime import datetime, timezone
            record = MagicMock()
            record.__getitem__ = lambda self, k: {
                "uuid": "c1", "content": "hello", "is_deleted": False,
                "created_at": datetime.now(timezone.utc), "updated_at": None,
                "author_email": "user@test.com", "author_fuid": "test-uid-123",
                "reply_count": 0, "reaction_emojis": [], "reaction_total": 0,
            }[k]
            count_record = MagicMock()
            count_record.__getitem__ = lambda self, k: {"total": 1}[k]

            comments_result = make_result([record])
            count_result = make_result()
            count_result.single = AsyncMock(return_value=count_record)

            session.run.side_effect = [comments_result, count_result]

            response = test_client.get("/ontologies/ont-1/comments")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["comments"]) == 1

    def test_edit_comment_forbidden(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver, session, make_result = _make_async_session()
            mock_get.return_value = driver

            not_found_result = make_result()
            not_found_result.single = AsyncMock(return_value=None)
            session.run.return_value = not_found_result

            response = test_client.put(
                "/comments/c1",
                json={"content": "edited"}
            )
            assert response.status_code == 403

    def test_delete_comment_forbidden(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver, session, make_result = _make_async_session()
            mock_get.return_value = driver

            auth_record = MagicMock()
            auth_record.__getitem__ = lambda self, k: {"authorized": False}[k]
            auth_result = make_result()
            auth_result.single = AsyncMock(return_value=auth_record)
            session.run.return_value = auth_result

            response = test_client.delete("/comments/c1")
            assert response.status_code == 403

    def test_create_reply_201(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver, session, make_result = _make_async_session()
            mock_get.return_value = driver

            record = MagicMock()
            record.__getitem__ = lambda self, k: {"root_uuid": "c1", "parent_uuid": "c1"}[k]
            found_result = make_result()
            found_result.single = AsyncMock(return_value=record)
            create_result = make_result()

            session.run.side_effect = [found_result, create_result]

            response = test_client.post(
                "/comments/c1/replies",
                json={"content": "Nice reply!"}
            )
            assert response.status_code == 201

    def test_get_replies(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver, session, make_result = _make_async_session()
            mock_get.return_value = driver

            from datetime import datetime, timezone
            record = MagicMock()
            record.__getitem__ = lambda self, k: {
                "uuid": "r1", "content": "reply", "is_deleted": False,
                "created_at": datetime.now(timezone.utc), "author_email": "user@test.com",
            }[k]
            session.run.return_value = make_result([record])

            response = test_client.get("/comments/c1/replies")
            assert response.status_code == 200

    def test_empty_comment_rejected(self, test_client, mock_neo4j_driver):
        response = test_client.post(
            "/ontologies/ont-1/comments",
            json={"content": ""}
        )
        assert response.status_code == 422

    def test_too_long_comment_rejected(self, test_client, mock_neo4j_driver):
        response = test_client.post(
            "/ontologies/ont-1/comments",
            json={"content": "a" * 2001}
        )
        assert response.status_code == 422
