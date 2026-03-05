import pytest
from unittest.mock import MagicMock, patch
from functions.flags import create_flag, check_user_has_flagged


@pytest.fixture
def mock_driver():
    with patch("functions.flags.get_neo4j_driver") as mock_get:
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = driver
        yield session


class TestCreateFlag:
    def test_success(self, mock_driver):
        mock_driver.run.side_effect = [
            MagicMock(single=MagicMock(return_value=None)),  # no duplicate
            MagicMock(),  # create
        ]
        result = create_flag("c1", "spam", None, "user-fuid")
        assert result["success"] is True
        assert result["status"] == 201

    def test_duplicate_prevention(self, mock_driver):
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {"uuid": "f1"}[k]
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=existing))
        result = create_flag("c1", "spam", None, "user-fuid")
        assert result["success"] is False
        assert result["status"] == 409


class TestCheckUserHasFlagged:
    def test_has_flagged(self, mock_driver):
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"uuid": "f1"}[k]
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=record))
        result = check_user_has_flagged("c1", "user-fuid")
        assert result["data"]["has_flagged"] is True

    def test_has_not_flagged(self, mock_driver):
        mock_driver.run.return_value = MagicMock(single=MagicMock(return_value=None))
        result = check_user_has_flagged("c1", "user-fuid")
        assert result["data"]["has_flagged"] is False
