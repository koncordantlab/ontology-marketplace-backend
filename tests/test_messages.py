import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from async_helpers import AsyncIteratorFromList
from functions.messages import send_message, get_messages, get_message, reply_to_message, mark_message_read


@pytest.fixture
def mock_driver():
    with patch("functions.messages.get_neo4j_driver") as mock_get:
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


class TestSendMessage:
    async def test_success(self, mock_driver):
        session = mock_driver._session
        session.run.return_value = mock_driver._make_result()
        result = await send_message("recipient-fuid", "Hello", "Body text", "admin-fuid", "admin@test.com")
        assert result["success"] is True
        assert result["status"] == 201


class TestGetMessages:
    async def test_returns_inbox(self, mock_driver):
        from datetime import datetime, timezone
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "m1", "subject": "Hi", "content": "Hello",
            "is_read": False, "created_at": datetime.now(timezone.utc),
            "sender_email": "admin@test.com",
        }[k]
        session.run.return_value = mock_driver._make_result([record])
        result = await get_messages("user-fuid")
        assert result["success"] is True
        assert len(result["data"]["messages"]) == 1


class TestGetMessage:
    async def test_found(self, mock_driver):
        from datetime import datetime, timezone
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "m1", "subject": "Hi", "content": "Hello",
            "is_read": False, "created_at": datetime.now(timezone.utc),
            "sender_email": "admin@test.com", "sender_fuid": "admin-fuid",
            "recipient_fuid": "user-fuid",
        }[k]
        msg_result = mock_driver._make_result()
        msg_result.single = AsyncMock(return_value=record)
        replies_result = mock_driver._make_result([])

        session.run.side_effect = [msg_result, replies_result]
        result = await get_message("m1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["subject"] == "Hi"

    async def test_not_found(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await get_message("nonexistent", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 404

    async def test_unauthorized(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "m1", "subject": "Hi", "content": "Hello",
            "is_read": False, "created_at": "now",
            "sender_email": "admin@test.com", "sender_fuid": "admin-fuid",
            "recipient_fuid": "other-user-fuid",
        }[k]
        msg_result = mock_driver._make_result()
        msg_result.single = AsyncMock(return_value=record)
        session.run.return_value = msg_result
        result = await get_message("m1", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 403


class TestReplyToMessage:
    async def test_recipient_can_reply(self, mock_driver):
        session = mock_driver._session
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        auth_result = mock_driver._make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        create_result = mock_driver._make_result()

        session.run.side_effect = [auth_result, create_result]
        result = await reply_to_message("m1", "Thanks!", "user-fuid", "user@test.com")
        assert result["success"] is True
        assert result["status"] == 201

    async def test_non_recipient_forbidden(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await reply_to_message("m1", "reply", "wrong-fuid", "wrong@test.com")
        assert result["success"] is False
        assert result["status"] == 403


class TestMarkMessageRead:
    async def test_success(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        found_result = mock_driver._make_result()
        found_result.single = AsyncMock(return_value=record)
        session.run.return_value = found_result
        result = await mark_message_read("m1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["is_read"] is True

    async def test_not_found(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await mark_message_read("m1", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 404
