import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from async_helpers import AsyncIteratorFromList
from functions.comments import (
    create_comment, get_comments, edit_comment, delete_comment,
    create_reply, get_replies
)
from datetime import datetime, timezone, timedelta


@pytest.fixture
def mock_driver():
    with patch("functions.comments.get_neo4j_driver") as mock_get:
        driver = MagicMock()

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

        mock_get.return_value = driver

        driver._session = session
        driver._make_result = make_result

        yield driver


class TestCreateComment:
    async def test_success(self, mock_driver):
        session = mock_driver._session
        # Ontology accessible
        ontology_record = MagicMock()
        ontology_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
        rate_record = MagicMock()
        rate_record.__getitem__ = lambda self, k: {"recent_count": 0}[k]

        ont_result = mock_driver._make_result()
        ont_result.single = AsyncMock(return_value=ontology_record)
        rate_result = mock_driver._make_result()
        rate_result.single = AsyncMock(return_value=rate_record)
        create_result = mock_driver._make_result()

        session.run.side_effect = [ont_result, rate_result, create_result]
        result = await create_comment("ont-1", "Great ontology!", "user-fuid", "user@test.com")
        assert result["success"] is True
        assert result["status"] == 201
        assert "uuid" in result["data"]

    async def test_ontology_not_found(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await create_comment("nonexistent", "comment", "user-fuid", "user@test.com")
        assert result["success"] is False
        assert result["status"] == 404

    async def test_rate_limit(self, mock_driver):
        session = mock_driver._session
        ontology_record = MagicMock()
        ontology_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
        rate_record = MagicMock()
        rate_record.__getitem__ = lambda self, k: {"recent_count": 6}[k]

        ont_result = mock_driver._make_result()
        ont_result.single = AsyncMock(return_value=ontology_record)
        rate_result = mock_driver._make_result()
        rate_result.single = AsyncMock(return_value=rate_record)

        session.run.side_effect = [ont_result, rate_result]
        result = await create_comment("ont-1", "comment", "user-fuid", "user@test.com")
        assert result["success"] is False
        assert result["status"] == 429


class TestGetComments:
    async def test_returns_comments(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "c1", "content": "hello", "is_deleted": False,
            "created_at": datetime.now(timezone.utc), "updated_at": None,
            "author_email": "user@test.com", "author_fuid": "fuid1",
            "reply_count": 0, "reaction_emojis": [], "reaction_total": 0,
        }[k]
        comments_result = mock_driver._make_result([record])
        count_record = MagicMock()
        count_record.__getitem__ = lambda self, k: {"total": 1}[k]
        count_result = mock_driver._make_result()
        count_result.single = AsyncMock(return_value=count_record)

        session.run.side_effect = [comments_result, count_result]
        result = await get_comments("ont-1")
        assert result["success"] is True
        assert len(result["data"]["comments"]) == 1
        assert result["data"]["total"] == 1

    async def test_pagination(self, mock_driver):
        session = mock_driver._session
        comments_result = mock_driver._make_result([])
        count_record = MagicMock()
        count_record.__getitem__ = lambda self, k: {"total": 0}[k]
        count_result = mock_driver._make_result()
        count_result.single = AsyncMock(return_value=count_record)

        session.run.side_effect = [comments_result, count_result]
        result = await get_comments("ont-1", limit=10, offset=5)
        assert result["success"] is True
        assert result["data"]["comments"] == []


class TestEditComment:
    async def test_within_window(self, mock_driver):
        session = mock_driver._session
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"created_at": recent}[k]
        found_result = mock_driver._make_result()
        found_result.single = AsyncMock(return_value=record)
        update_result = mock_driver._make_result()

        session.run.side_effect = [found_result, update_result]
        result = await edit_comment("c1", "updated content", "user-fuid")
        assert result["success"] is True

    async def test_past_window(self, mock_driver):
        session = mock_driver._session
        old = datetime.now(timezone.utc) - timedelta(minutes=20)
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"created_at": old}[k]
        found_result = mock_driver._make_result()
        found_result.single = AsyncMock(return_value=record)
        session.run.return_value = found_result
        result = await edit_comment("c1", "updated content", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 403

    async def test_not_author(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await edit_comment("c1", "content", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 403


class TestDeleteComment:
    async def test_hard_delete_no_deps(self, mock_driver):
        session = mock_driver._session
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": True}[k]
        dep_record = MagicMock()
        dep_record.__getitem__ = lambda self, k: {"dep_count": 0}[k]

        auth_result = mock_driver._make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        dep_result = mock_driver._make_result()
        dep_result.single = AsyncMock(return_value=dep_record)
        delete_result = mock_driver._make_result()

        session.run.side_effect = [auth_result, dep_result, delete_result]
        result = await delete_comment("c1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["hard_deleted"] is True

    async def test_soft_delete_with_deps(self, mock_driver):
        session = mock_driver._session
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": True}[k]
        dep_record = MagicMock()
        dep_record.__getitem__ = lambda self, k: {"dep_count": 3}[k]

        auth_result = mock_driver._make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        dep_result = mock_driver._make_result()
        dep_result.single = AsyncMock(return_value=dep_record)
        soft_delete_result = mock_driver._make_result()

        session.run.side_effect = [auth_result, dep_result, soft_delete_result]
        result = await delete_comment("c1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["hard_deleted"] is False

    async def test_unauthorized(self, mock_driver):
        session = mock_driver._session
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": False}[k]
        auth_result = mock_driver._make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        session.run.return_value = auth_result
        result = await delete_comment("c1", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 403


class TestCreateReply:
    async def test_success(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"root_uuid": "c1", "parent_uuid": "c1"}[k]
        found_result = mock_driver._make_result()
        found_result.single = AsyncMock(return_value=record)
        create_result = mock_driver._make_result()

        session.run.side_effect = [found_result, create_result]
        result = await create_reply("c1", "nice reply", "user-fuid", "user@test.com")
        assert result["success"] is True
        assert result["status"] == 201

    async def test_flatten_nested(self, mock_driver):
        """If replying to a reply, it flattens to the root comment."""
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"root_uuid": "root-c", "parent_uuid": "reply-c"}[k]
        found_result = mock_driver._make_result()
        found_result.single = AsyncMock(return_value=record)
        create_result = mock_driver._make_result()

        session.run.side_effect = [found_result, create_result]
        result = await create_reply("reply-c", "nested reply", "user-fuid", "user@test.com")
        assert result["success"] is True

    async def test_parent_not_found(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await create_reply("nonexistent", "reply", "user-fuid", "user@test.com")
        assert result["success"] is False
        assert result["status"] == 404


class TestGetReplies:
    async def test_returns_replies(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "r1", "content": "reply text", "is_deleted": False,
            "created_at": datetime.now(timezone.utc), "author_email": "user@test.com",
        }[k]
        session.run.return_value = mock_driver._make_result([record])
        result = await get_replies("c1")
        assert result["success"] is True
        assert len(result["data"]["replies"]) == 1
