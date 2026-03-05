import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from async_helpers import AsyncIteratorFromList
from functions.flags import create_flag, check_user_has_flagged


@pytest.fixture
def mock_driver():
    with patch("functions.flags.get_neo4j_driver") as mock_get:
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


class TestCreateFlag:
    async def test_success(self, mock_driver):
        session = mock_driver._session
        no_dup = mock_driver._make_result()
        no_dup.single = AsyncMock(return_value=None)
        create_result = mock_driver._make_result()

        session.run.side_effect = [no_dup, create_result]
        result = await create_flag("c1", "spam", None, "user-fuid")
        assert result["success"] is True
        assert result["status"] == 201

    async def test_duplicate_prevention(self, mock_driver):
        session = mock_driver._session
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {"uuid": "f1"}[k]
        dup_result = mock_driver._make_result()
        dup_result.single = AsyncMock(return_value=existing)
        session.run.return_value = dup_result
        result = await create_flag("c1", "spam", None, "user-fuid")
        assert result["success"] is False
        assert result["status"] == 409


class TestCheckUserHasFlagged:
    async def test_has_flagged(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"uuid": "f1"}[k]
        found_result = mock_driver._make_result()
        found_result.single = AsyncMock(return_value=record)
        session.run.return_value = found_result
        result = await check_user_has_flagged("c1", "user-fuid")
        assert result["data"]["has_flagged"] is True

    async def test_has_not_flagged(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await check_user_has_flagged("c1", "user-fuid")
        assert result["data"]["has_flagged"] is False
