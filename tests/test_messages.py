import pytest
from unittest.mock import MagicMock, patch
from functions.messages import send_message, get_messages, get_message, reply_to_message, mark_message_read


@pytest.fixture
def mock_driver():
    with patch("functions.messages.get_neo4j_driver") as mock_get:
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = driver
        yield session


class TestSendMessage:
    def test_success(self, mock_driver):
        mock_driver.run.return_value = MagicMock()
        result = send_message("recipient-fuid", "Hello", "Body text", "admin-fuid", "admin@test.com")
        assert result["success"] is True
        assert result["status"] == 201


class TestGetMessages:
    def test_returns_inbox(self, mock_driver):
        from datetime import datetime, timezone
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "m1", "subject": "Hi", "content": "Hello",
            "is_read": False, "created_at": datetime.now(timezone.utc),
            "sender_email": "admin@test.com",
        }[k]
        mock_driver.run.return_value = MagicMock(__iter__=lambda s: iter([record]))
        result = get_messages("user-fuid")
        assert result["success"] is True
        assert len(result["data"]["messages"]) == 1


class TestGetMessage:
    def test_found(self, mock_driver):
        from datetime import datetime, timezone
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "m1", "subject": "Hi", "content": "Hello",
            "is_read": False, "created_at": datetime.now(timezone.utc),
            "sender_email": "admin@test.com", "sender_fuid": "admin-fuid",
            "recipient_fuid": "user-fuid",
        }[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=record)),
            MagicMock(__iter__=lambda s: iter([])),  # no replies
        ]
        result = get_message("m1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["subject"] == "Hi"

    def test_not_found(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = get_message("nonexistent", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 404

    def test_unauthorized(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "m1", "subject": "Hi", "content": "Hello",
            "is_read": False, "created_at": "now",
            "sender_email": "admin@test.com", "sender_fuid": "admin-fuid",
            "recipient_fuid": "other-user-fuid",
        }[k]
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=record))
        result = get_message("m1", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 403


class TestReplyToMessage:
    def test_recipient_can_reply(self, mock_driver):
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=auth_record)),
            MagicMock(),
        ]
        result = reply_to_message("m1", "Thanks!", "user-fuid", "user@test.com")
        assert result["success"] is True
        assert result["status"] == 201

    def test_non_recipient_forbidden(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = reply_to_message("m1", "reply", "wrong-fuid", "wrong@test.com")
        assert result["success"] is False
        assert result["status"] == 403


class TestMarkMessageRead:
    def test_success(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=record))
        result = mark_message_read("m1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["is_read"] is True

    def test_not_found(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = mark_message_read("m1", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 404
