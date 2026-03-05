import pytest
from unittest.mock import MagicMock, patch
from functions.comments import (
    create_comment, get_comments, edit_comment, delete_comment,
    create_reply, get_replies
)
from datetime import datetime, timezone, timedelta


@pytest.fixture
def mock_driver():
    with patch("functions.comments.get_neo4j_driver") as mock_get:
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = driver
        yield session


class TestCreateComment:
    def test_success(self, mock_driver):
        # Ontology accessible
        ontology_record = MagicMock()
        ontology_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=ontology_record)),  # ontology check
            MagicMock(single=MagicMock(return_value=MagicMock(__getitem__=lambda s, k: 0))),  # rate limit
            MagicMock(),  # create
        ]
        result = create_comment("ont-1", "Great ontology!", "user-fuid", "user@test.com")
        assert result["success"] is True
        assert result["status"] == 201
        assert "uuid" in result["data"]

    def test_ontology_not_found(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = create_comment("nonexistent", "comment", "user-fuid", "user@test.com")
        assert result["success"] is False
        assert result["status"] == 404

    def test_rate_limit(self, mock_driver):
        ontology_record = MagicMock()
        ontology_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
        rate_record = MagicMock()
        rate_record.__getitem__ = lambda self, k: {"recent_count": 6}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=ontology_record)),
            MagicMock(single=MagicMock(return_value=rate_record)),
        ]
        result = create_comment("ont-1", "comment", "user-fuid", "user@test.com")
        assert result["success"] is False
        assert result["status"] == 429


class TestGetComments:
    def test_returns_comments(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "c1", "content": "hello", "is_deleted": False,
            "created_at": datetime.now(timezone.utc), "updated_at": None,
            "author_email": "user@test.com", "author_fuid": "fuid1",
            "reply_count": 0, "reaction_emojis": [], "reaction_total": 0,
        }[k]
        count_record = MagicMock()
        count_record.__getitem__ = lambda self, k: {"total": 1}[k]
        mock_driver.run.side_effect = [
            MagicMock(__iter__=lambda s: iter([record])),
            MagicMock(single=MagicMock(return_value=count_record)),
        ]
        result = get_comments("ont-1")
        assert result["success"] is True
        assert len(result["data"]["comments"]) == 1
        assert result["data"]["total"] == 1

    def test_pagination(self, mock_driver):
        count_record = MagicMock()
        count_record.__getitem__ = lambda self, k: {"total": 0}[k]
        mock_driver.run.side_effect = [
            MagicMock(__iter__=lambda s: iter([])),
            MagicMock(single=MagicMock(return_value=count_record)),
        ]
        result = get_comments("ont-1", limit=10, offset=5)
        assert result["success"] is True
        assert result["data"]["comments"] == []


class TestEditComment:
    def test_within_window(self, mock_driver):
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"created_at": recent}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=record)),
            MagicMock(),
        ]
        result = edit_comment("c1", "updated content", "user-fuid")
        assert result["success"] is True

    def test_past_window(self, mock_driver):
        old = datetime.now(timezone.utc) - timedelta(minutes=20)
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"created_at": old}[k]
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=record))
        result = edit_comment("c1", "updated content", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 403

    def test_not_author(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = edit_comment("c1", "content", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 403


class TestDeleteComment:
    def test_hard_delete_no_deps(self, mock_driver):
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": True}[k]
        dep_record = MagicMock()
        dep_record.__getitem__ = lambda self, k: {"dep_count": 0}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=auth_record)),
            MagicMock(single=MagicMock(return_value=dep_record)),
            MagicMock(),
        ]
        result = delete_comment("c1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["hard_deleted"] is True

    def test_soft_delete_with_deps(self, mock_driver):
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": True}[k]
        dep_record = MagicMock()
        dep_record.__getitem__ = lambda self, k: {"dep_count": 3}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=auth_record)),
            MagicMock(single=MagicMock(return_value=dep_record)),
            MagicMock(),
        ]
        result = delete_comment("c1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["hard_deleted"] is False

    def test_unauthorized(self, mock_driver):
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": False}[k]
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=auth_record))
        result = delete_comment("c1", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 403


class TestCreateReply:
    def test_success(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"root_uuid": "c1", "parent_uuid": "c1"}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=record)),
            MagicMock(),
        ]
        result = create_reply("c1", "nice reply", "user-fuid", "user@test.com")
        assert result["success"] is True
        assert result["status"] == 201

    def test_flatten_nested(self, mock_driver):
        """If replying to a reply, it flattens to the root comment."""
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"root_uuid": "root-c", "parent_uuid": "reply-c"}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=record)),
            MagicMock(),
        ]
        result = create_reply("reply-c", "nested reply", "user-fuid", "user@test.com")
        assert result["success"] is True

    def test_parent_not_found(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = create_reply("nonexistent", "reply", "user-fuid", "user@test.com")
        assert result["success"] is False
        assert result["status"] == 404


class TestGetReplies:
    def test_returns_replies(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "r1", "content": "reply text", "is_deleted": False,
            "created_at": datetime.now(timezone.utc), "author_email": "user@test.com",
        }[k]
        mock_driver.run.return_value = MagicMock(__iter__=lambda s: iter([record]))
        result = get_replies("c1")
        assert result["success"] is True
        assert len(result["data"]["replies"]) == 1
