import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from async_helpers import AsyncIteratorFromList
from functions.activity import get_activity_feed, get_unread_count, mark_read, mark_all_read


@pytest.fixture
def mock_driver():
    with patch("functions.activity.get_neo4j_driver") as mock_get:
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


class TestGetActivityFeed:
    async def test_returns_items(self, mock_driver):
        from datetime import datetime, timezone
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "id": "a1", "type": "comment", "created_at": datetime.now(timezone.utc),
            "content": "hello", "subject": None, "ontology_name": "Test Onto",
            "ontology_id": "ont-1", "is_read": False,
        }[k]
        session.run.return_value = mock_driver._make_result([record])
        result = await get_activity_feed("user-fuid")
        assert result["success"] is True
        assert len(result["data"]["items"]) == 1
        # Verify single query pattern (UNION ALL in CALL {} block)
        assert session.run.call_count == 1

    async def test_type_filter(self, mock_driver):
        session = mock_driver._session
        session.run.return_value = mock_driver._make_result([])
        result = await get_activity_feed("user-fuid", type_filter="message")
        assert result["success"] is True

    async def test_empty_feed(self, mock_driver):
        session = mock_driver._session
        session.run.return_value = mock_driver._make_result([])
        result = await get_activity_feed("user-fuid")
        assert result["success"] is True
        assert result["data"]["items"] == []


class TestGetUnreadCount:
    async def test_count(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"count": 5}[k]
        result_mock = mock_driver._make_result()
        result_mock.single = AsyncMock(return_value=record)
        session.run.return_value = result_mock
        result = await get_unread_count("user-fuid")
        assert result["data"]["count"] == 5


class TestMarkRead:
    async def test_mark_message(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        result_mock = mock_driver._make_result()
        result_mock.single = AsyncMock(return_value=record)
        session.run.return_value = result_mock
        result = await mark_read("m1", "user-fuid")
        assert result["success"] is True

    async def test_not_found(self, mock_driver):
        session = mock_driver._session
        result_mock = mock_driver._make_result()
        result_mock.single = AsyncMock(return_value=None)
        session.run.return_value = result_mock
        result = await mark_read("nonexistent", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 404


class TestMarkAllRead:
    async def test_success(self, mock_driver):
        session = mock_driver._session
        session.run.return_value = mock_driver._make_result()
        result = await mark_all_read("user-fuid")
        assert result["success"] is True
        assert result["data"]["marked_all_read"] is True
