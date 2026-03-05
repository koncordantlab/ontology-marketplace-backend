import pytest
from unittest.mock import MagicMock, patch
from functions.reactions import toggle_reaction, remove_reaction, remove_reaction_by_owner, get_reaction_counts


@pytest.fixture
def mock_driver():
    with patch("functions.reactions.get_neo4j_driver") as mock_get:
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = driver
        yield session


class TestToggleReaction:
    def test_add_reaction(self, mock_driver):
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=None)),  # no existing
            MagicMock(),  # create
        ]
        result = toggle_reaction("c1", "👍", "user-fuid")
        assert result["success"] is True
        assert result["data"]["action"] == "added"
        assert result["status"] == 201

    def test_remove_existing_reaction(self, mock_driver):
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {"uuid": "r1"}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=existing)),  # existing found
            MagicMock(),  # delete
        ]
        result = toggle_reaction("c1", "👍", "user-fuid")
        assert result["success"] is True
        assert result["data"]["action"] == "removed"

    def test_invalid_emoji(self, mock_driver):
        result = toggle_reaction("c1", "🤔", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 400


class TestRemoveReaction:
    def test_remove_own(self, mock_driver):
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {"uuid": "r1"}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=existing)),
            MagicMock(),
        ]
        result = remove_reaction("c1", "👍", "user-fuid")
        assert result["success"] is True

    def test_not_found(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = remove_reaction("c1", "👍", "user-fuid")
        assert result["success"] is False
        assert result["status"] == 404


class TestRemoveReactionByOwner:
    def test_owner_can_remove(self, mock_driver):
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"uuid": "r1"}[k]
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=auth_record)),
            MagicMock(),
        ]
        result = remove_reaction_by_owner("c1", "r1", "owner-fuid")
        assert result["success"] is True

    def test_unauthorized(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = remove_reaction_by_owner("c1", "r1", "wrong-fuid")
        assert result["success"] is False
        assert result["status"] == 403


class TestGetReactionCounts:
    def test_aggregated_counts(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "emoji": "👍", "count": 3, "user_fuids": ["user-fuid", "other"]
        }[k]
        mock_driver.run.return_value = MagicMock(__iter__=lambda s: iter([record]))
        result = get_reaction_counts("c1", user_fuid="user-fuid")
        assert result["success"] is True
        assert result["data"]["👍"]["count"] == 3
        assert result["data"]["👍"]["user_reacted"] is True

    def test_no_reactions(self, mock_driver):
        mock_driver.run.return_value = MagicMock(__iter__=lambda s: iter([]))
        result = get_reaction_counts("c1")
        assert result["success"] is True
        assert result["data"] == {}
