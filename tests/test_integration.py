"""Integration tests for full community feature workflows."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta


@pytest.fixture
def mock_session():
    """Shared mock session for integration tests."""
    session = MagicMock()
    return session


@pytest.fixture
def mock_all_drivers(mock_session):
    """Patch get_neo4j_driver in all modules."""
    driver = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)

    with patch("functions.comments.get_neo4j_driver", return_value=driver), \
         patch("functions.reactions.get_neo4j_driver", return_value=driver), \
         patch("functions.flags.get_neo4j_driver", return_value=driver), \
         patch("functions.messages.get_neo4j_driver", return_value=driver), \
         patch("functions.activity.get_neo4j_driver", return_value=driver):
        yield mock_session


class TestCommentLifecycle:
    """Test full comment lifecycle: create -> react -> reply -> edit -> delete."""

    def test_create_and_get_comment(self, mock_all_drivers):
        from functions.comments import create_comment, get_comments

        session = mock_all_drivers

        # Step 1: Create comment
        ont_record = MagicMock()
        ont_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
        rate_record = MagicMock()
        rate_record.__getitem__ = lambda self, k: {"recent_count": 0}[k]
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=ont_record)),
            MagicMock(single=MagicMock(return_value=rate_record)),
            MagicMock(),
        ]
        result = create_comment("ont-1", "My first comment", "user-fuid", "user@test.com")
        assert result["success"] is True
        assert result["status"] == 201
        comment_uuid = result["data"]["uuid"]
        assert comment_uuid is not None

    def test_create_react_and_check_counts(self, mock_all_drivers):
        from functions.reactions import toggle_reaction, get_reaction_counts

        session = mock_all_drivers

        # Toggle reaction (add)
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=None)),  # no existing
            MagicMock(),  # create
        ]
        result = toggle_reaction("c1", "👍", "user-fuid")
        assert result["success"] is True
        assert result["data"]["action"] == "added"

        # Check counts
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "emoji": "👍", "count": 1, "user_fuids": ["user-fuid"]
        }[k]
        session.run.side_effect = None
        session.run.return_value = MagicMock(__iter__=lambda s: iter([record]))
        counts = get_reaction_counts("c1", "user-fuid")
        assert counts["data"]["👍"]["count"] == 1
        assert counts["data"]["👍"]["user_reacted"] is True

    def test_create_reply_then_soft_delete(self, mock_all_drivers):
        from functions.comments import create_reply, delete_comment

        session = mock_all_drivers

        # Create reply
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"root_uuid": "c1", "parent_uuid": "c1"}[k]
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=record)),
            MagicMock(),
        ]
        result = create_reply("c1", "Nice!", "user2-fuid", "user2@test.com")
        assert result["success"] is True

        # Delete parent (should soft-delete because it has replies)
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": True}[k]
        dep_record = MagicMock()
        dep_record.__getitem__ = lambda self, k: {"dep_count": 1}[k]
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=auth_record)),
            MagicMock(single=MagicMock(return_value=dep_record)),
            MagicMock(),
        ]
        result = delete_comment("c1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["hard_deleted"] is False

    def test_flag_then_duplicate_prevented(self, mock_all_drivers):
        from functions.flags import create_flag

        session = mock_all_drivers

        # First flag succeeds
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=None)),
            MagicMock(),
        ]
        result = create_flag("c1", "spam", None, "user-fuid")
        assert result["success"] is True

        # Second flag fails (duplicate)
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {"uuid": "f1"}[k]
        session.run.side_effect = None
        session.run.return_value = MagicMock(single=MagicMock(return_value=existing))
        result = create_flag("c1", "spam", None, "user-fuid")
        assert result["success"] is False
        assert result["status"] == 409


class TestAdminMessageWorkflow:
    """Test admin message workflow: send -> inbox -> read -> reply."""

    def test_full_message_flow(self, mock_all_drivers):
        from functions.messages import send_message, get_messages, get_message, reply_to_message, mark_message_read

        session = mock_all_drivers

        # Admin sends message
        session.run.return_value = MagicMock()
        result = send_message("user-fuid", "Welcome", "Hello user!", "admin-fuid", "admin@test.com")
        assert result["success"] is True

        # User checks inbox
        from datetime import datetime, timezone
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "m1", "subject": "Welcome", "content": "Hello user!",
            "is_read": False, "created_at": datetime.now(timezone.utc),
            "sender_email": "admin@test.com",
        }[k]
        session.run.return_value = MagicMock(__iter__=lambda s: iter([record]))
        inbox = get_messages("user-fuid")
        assert inbox["success"] is True
        assert len(inbox["data"]["messages"]) == 1
        assert inbox["data"]["messages"][0]["is_read"] is False

        # User marks as read
        read_record = MagicMock()
        read_record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        session.run.return_value = MagicMock(single=MagicMock(return_value=read_record))
        result = mark_message_read("m1", "user-fuid")
        assert result["success"] is True

        # User replies
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=auth_record)),
            MagicMock(),
        ]
        result = reply_to_message("m1", "Thanks admin!", "user-fuid", "user@test.com")
        assert result["success"] is True


class TestOwnerModeration:
    """Test ontology owner's moderation capabilities."""

    def test_owner_can_delete_any_comment(self, mock_all_drivers):
        from functions.comments import delete_comment

        session = mock_all_drivers
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": True}[k]
        dep_record = MagicMock()
        dep_record.__getitem__ = lambda self, k: {"dep_count": 0}[k]
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=auth_record)),
            MagicMock(single=MagicMock(return_value=dep_record)),
            MagicMock(),
        ]
        result = delete_comment("c1", "owner-fuid")
        assert result["success"] is True
        assert result["data"]["hard_deleted"] is True

    def test_owner_can_remove_reaction(self, mock_all_drivers):
        from functions.reactions import remove_reaction_by_owner

        session = mock_all_drivers
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"uuid": "r1"}[k]
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=auth_record)),
            MagicMock(),
        ]
        result = remove_reaction_by_owner("c1", "r1", "owner-fuid")
        assert result["success"] is True
