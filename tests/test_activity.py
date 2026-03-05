import pytest
from unittest.mock import MagicMock, patch
from functions.activity import get_activity_feed, get_unread_count, mark_read, mark_all_read


@pytest.fixture
def mock_driver():
    with patch("functions.activity.get_neo4j_driver") as mock_get:
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = driver
        yield session


class TestGetActivityFeed:
    def test_returns_items(self, mock_driver):
        from datetime import datetime, timezone
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "id": "a1", "type": "comment", "created_at": datetime.now(timezone.utc),
            "content": "hello", "subject": None, "ontology_name": "Test Onto",
            "ontology_id": "ont-1", "is_read": False,
        }[k]
        mock_driver.run.return_value = MagicMock(__iter__=lambda s: iter([record]))
        result = get_activity_feed("user-fuid")
        assert result["success"] is True
        assert len(result["data"]["items"]) == 1

    def test_type_filter(self, mock_driver):
        mock_driver.run.return_value = MagicMock(__iter__=lambda s: iter([]))
        result = get_activity_feed("user-fuid", type_filter="message")
        assert result["success"] is True

    def test_empty_feed(self, mock_driver):
        mock_driver.run.return_value = MagicMock(__iter__=lambda s: iter([]))
        result = get_activity_feed("user-fuid")
        assert result["success"] is True
        assert result["data"]["items"] == []


class TestGetUnreadCount:
    def test_count(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"count": 5}[k]
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=record))
        result = get_unread_count("user-fuid")
        assert result["data"]["count"] == 5


class TestMarkRead:
    def test_mark_message(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=record))
        result = mark_read("m1", "user-fuid")
        assert result["success"] is True

    def test_not_found(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = mark_read("nonexistent", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 404


class TestMarkAllRead:
    def test_success(self, mock_driver):
        mock_driver.run.return_value = MagicMock()
        result = mark_all_read("user-fuid")
        assert result["success"] is True
        assert result["data"]["marked_all_read"] is True
