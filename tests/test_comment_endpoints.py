import pytest
from unittest.mock import patch, MagicMock


class TestCommentEndpoints:
    def test_create_comment_201(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver = MagicMock()
            session = MagicMock()
            driver.session.return_value.__enter__ = MagicMock(return_value=session)
            driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = driver

            # Mock ontology accessible
            ont_record = MagicMock()
            ont_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
            rate_record = MagicMock()
            rate_record.__getitem__ = lambda self, k: {"recent_count": 0}[k]
            session.run.side_effect = [
                MagicMock(single=MagicMock(return_value=ont_record)),
                MagicMock(single=MagicMock(return_value=rate_record)),
                MagicMock(),
            ]

            response = test_client.post(
                "/ontologies/ont-1/comments",
                json={"content": "Great ontology!"}
            )
            assert response.status_code == 201
            assert response.json()["success"] is True

    def test_create_comment_rate_limit_429(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver = MagicMock()
            session = MagicMock()
            driver.session.return_value.__enter__ = MagicMock(return_value=session)
            driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = driver

            ont_record = MagicMock()
            ont_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
            rate_record = MagicMock()
            rate_record.__getitem__ = lambda self, k: {"recent_count": 6}[k]
            session.run.side_effect = [
                MagicMock(single=MagicMock(return_value=ont_record)),
                MagicMock(single=MagicMock(return_value=rate_record)),
            ]

            response = test_client.post(
                "/ontologies/ont-1/comments",
                json={"content": "Too many comments"}
            )
            assert response.status_code == 429

    def test_get_comments(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver = MagicMock()
            session = MagicMock()
            driver.session.return_value.__enter__ = MagicMock(return_value=session)
            driver.session.return_value.__exit__ = MagicMock(return_value=False)
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
            session.run.side_effect = [
                MagicMock(__iter__=lambda s: iter([record])),
                MagicMock(single=MagicMock(return_value=count_record)),
            ]

            response = test_client.get("/ontologies/ont-1/comments")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["comments"]) == 1

    def test_edit_comment_forbidden(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver = MagicMock()
            session = MagicMock()
            driver.session.return_value.__enter__ = MagicMock(return_value=session)
            driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = driver

            session.run.return_value = MagicMock(single=MagicMock(return_value=None))

            response = test_client.put(
                "/comments/c1",
                json={"content": "edited"}
            )
            assert response.status_code == 403

    def test_delete_comment_forbidden(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver = MagicMock()
            session = MagicMock()
            driver.session.return_value.__enter__ = MagicMock(return_value=session)
            driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = driver

            auth_record = MagicMock()
            auth_record.__getitem__ = lambda self, k: {"authorized": False}[k]
            session.run.return_value = MagicMock(single=MagicMock(return_value=auth_record))

            response = test_client.delete("/comments/c1")
            assert response.status_code == 403

    def test_create_reply_201(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver = MagicMock()
            session = MagicMock()
            driver.session.return_value.__enter__ = MagicMock(return_value=session)
            driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = driver

            record = MagicMock()
            record.__getitem__ = lambda self, k: {"root_uuid": "c1", "parent_uuid": "c1"}[k]
            session.run.side_effect = [
                MagicMock(single=MagicMock(return_value=record)),
                MagicMock(),
            ]

            response = test_client.post(
                "/comments/c1/replies",
                json={"content": "Nice reply!"}
            )
            assert response.status_code == 201

    def test_get_replies(self, test_client, mock_neo4j_driver):
        with patch("functions.comments.get_neo4j_driver") as mock_get:
            driver = MagicMock()
            session = MagicMock()
            driver.session.return_value.__enter__ = MagicMock(return_value=session)
            driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = driver

            from datetime import datetime, timezone
            record = MagicMock()
            record.__getitem__ = lambda self, k: {
                "uuid": "r1", "content": "reply", "is_deleted": False,
                "created_at": datetime.now(timezone.utc), "author_email": "user@test.com",
            }[k]
            session.run.return_value = MagicMock(__iter__=lambda s: iter([record]))

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
