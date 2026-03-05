import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from async_helpers import AsyncIteratorFromList
from functions.reactions import toggle_reaction, remove_reaction, remove_reaction_by_owner, get_reaction_counts


@pytest.fixture
def mock_driver():
    with patch("functions.reactions.get_neo4j_driver") as mock_get:
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


class TestToggleReaction:
    async def test_add_reaction(self, mock_driver):
        session = mock_driver._session
        no_existing = mock_driver._make_result()
        no_existing.single = AsyncMock(return_value=None)
        create_result = mock_driver._make_result()

        session.run.side_effect = [no_existing, create_result]
        result = await toggle_reaction("c1", "\U0001f44d", "user-fuid")
        assert result["success"] is True
        assert result["data"]["action"] == "added"
        assert result["status"] == 201

    async def test_remove_existing_reaction(self, mock_driver):
        session = mock_driver._session
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {"uuid": "r1"}[k]
        found_result = mock_driver._make_result()
        found_result.single = AsyncMock(return_value=existing)
        delete_result = mock_driver._make_result()

        session.run.side_effect = [found_result, delete_result]
        result = await toggle_reaction("c1", "\U0001f44d", "user-fuid")
        assert result["success"] is True
        assert result["data"]["action"] == "removed"

    async def test_invalid_emoji(self, mock_driver):
        result = await toggle_reaction("c1", "\U0001f914", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 400


class TestRemoveReaction:
    async def test_remove_own(self, mock_driver):
        session = mock_driver._session
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {"uuid": "r1"}[k]
        found_result = mock_driver._make_result()
        found_result.single = AsyncMock(return_value=existing)
        delete_result = mock_driver._make_result()

        session.run.side_effect = [found_result, delete_result]
        result = await remove_reaction("c1", "\U0001f44d", "user-fuid")
        assert result["success"] is True

    async def test_not_found(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await remove_reaction("c1", "\U0001f44d", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 404


class TestRemoveReactionByOwner:
    async def test_owner_can_remove(self, mock_driver):
        session = mock_driver._session
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"uuid": "r1"}[k]
        auth_result = mock_driver._make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        delete_result = mock_driver._make_result()

        session.run.side_effect = [auth_result, delete_result]
        result = await remove_reaction_by_owner("c1", "r1", "owner-fuid")
        assert result["success"] is True

    async def test_unauthorized(self, mock_driver):
        session = mock_driver._session
        not_found_result = mock_driver._make_result()
        not_found_result.single = AsyncMock(return_value=None)
        session.run.return_value = not_found_result
        result = await remove_reaction_by_owner("c1", "r1", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 403


class TestGetReactionCounts:
    async def test_aggregated_counts(self, mock_driver):
        session = mock_driver._session
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "emoji": "\U0001f44d", "count": 3, "user_fuids": ["user-fuid", "other"]
        }[k]
        session.run.return_value = mock_driver._make_result([record])
        result = await get_reaction_counts("c1", user_fuid="user-fuid")
        assert result["success"] is True
        assert result["data"]["\U0001f44d"]["count"] == 3
        assert result["data"]["\U0001f44d"]["user_reacted"] is True

    async def test_no_reactions(self, mock_driver):
        session = mock_driver._session
        session.run.return_value = mock_driver._make_result([])
        result = await get_reaction_counts("c1")
        assert result["success"] is True
        assert result["data"] == {}
