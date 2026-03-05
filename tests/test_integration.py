"""Integration tests for full community feature workflows."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from async_helpers import AsyncIteratorFromList
from datetime import datetime, timezone, timedelta


def _make_async_driver_and_session():
    """Create an async-compatible driver + session pair."""
    def make_result(data=None):
        if data is None:
            data = []
        result = AsyncMock(name="neo4j_result")
        result.single = AsyncMock(return_value=None)
        result.__aiter__ = lambda self=None, d=data: AsyncIteratorFromList(d)
        return result

    driver = MagicMock()
    session = AsyncMock(name="neo4j_session")
    session.run = AsyncMock(return_value=make_result())

    session_ctx = AsyncMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=False)
    driver.session = MagicMock(return_value=session_ctx)

    return driver, session, make_result


@pytest.fixture
def mock_all_drivers():
    """Patch get_neo4j_driver in all modules."""
    driver, session, make_result = _make_async_driver_and_session()

    with patch("functions.comments.get_neo4j_driver", return_value=driver), \
         patch("functions.reactions.get_neo4j_driver", return_value=driver), \
         patch("functions.flags.get_neo4j_driver", return_value=driver), \
         patch("functions.messages.get_neo4j_driver", return_value=driver), \
         patch("functions.activity.get_neo4j_driver", return_value=driver):
        yield session, make_result


class TestCommentLifecycle:
    """Test full comment lifecycle: create -> react -> reply -> edit -> delete."""

    async def test_create_and_get_comment(self, mock_all_drivers):
        from functions.comments import create_comment, get_comments

        session, make_result = mock_all_drivers

        # Step 1: Create comment
        ont_record = MagicMock()
        ont_record.__getitem__ = lambda self, k: {"oid": "ont-1", "user_uuid": "u1"}[k]
        rate_record = MagicMock()
        rate_record.__getitem__ = lambda self, k: {"recent_count": 0}[k]

        ont_result = make_result()
        ont_result.single = AsyncMock(return_value=ont_record)
        rate_result = make_result()
        rate_result.single = AsyncMock(return_value=rate_record)
        create_result = make_result()

        session.run.side_effect = [ont_result, rate_result, create_result]
        result = await create_comment("ont-1", "My first comment", "user-fuid", "user@test.com")
        assert result["success"] is True
        assert result["status"] == 201
        comment_uuid = result["data"]["uuid"]
        assert comment_uuid is not None

    async def test_create_react_and_check_counts(self, mock_all_drivers):
        from functions.reactions import toggle_reaction, get_reaction_counts

        session, make_result = mock_all_drivers

        # Toggle reaction (add)
        no_existing = make_result()
        no_existing.single = AsyncMock(return_value=None)
        create_result = make_result()

        session.run.side_effect = [no_existing, create_result]
        result = await toggle_reaction("c1", "\U0001f44d", "user-fuid")
        assert result["success"] is True
        assert result["data"]["action"] == "added"

        # Check counts
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "emoji": "\U0001f44d", "count": 1, "user_fuids": ["user-fuid"]
        }[k]
        session.run.side_effect = None
        session.run.return_value = make_result([record])
        counts = await get_reaction_counts("c1", "user-fuid")
        assert counts["data"]["\U0001f44d"]["count"] == 1
        assert counts["data"]["\U0001f44d"]["user_reacted"] is True

    async def test_create_reply_then_soft_delete(self, mock_all_drivers):
        from functions.comments import create_reply, delete_comment

        session, make_result = mock_all_drivers

        # Create reply
        record = MagicMock()
        record.__getitem__ = lambda self, k: {"root_uuid": "c1", "parent_uuid": "c1"}[k]
        found_result = make_result()
        found_result.single = AsyncMock(return_value=record)
        create_result = make_result()

        session.run.side_effect = [found_result, create_result]
        result = await create_reply("c1", "Nice!", "user2-fuid", "user2@test.com")
        assert result["success"] is True

        # Delete parent (should soft-delete because it has replies)
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": True}[k]
        dep_record = MagicMock()
        dep_record.__getitem__ = lambda self, k: {"dep_count": 1}[k]

        auth_result = make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        dep_result = make_result()
        dep_result.single = AsyncMock(return_value=dep_record)
        soft_delete_result = make_result()

        session.run.side_effect = [auth_result, dep_result, soft_delete_result]
        result = await delete_comment("c1", "user-fuid")
        assert result["success"] is True
        assert result["data"]["hard_deleted"] is False

    async def test_flag_then_duplicate_prevented(self, mock_all_drivers):
        from functions.flags import create_flag

        session, make_result = mock_all_drivers

        # First flag succeeds
        no_dup = make_result()
        no_dup.single = AsyncMock(return_value=None)
        create_result = make_result()

        session.run.side_effect = [no_dup, create_result]
        result = await create_flag("c1", "spam", None, "user-fuid")
        assert result["success"] is True

        # Second flag fails (duplicate)
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {"uuid": "f1"}[k]
        dup_result = make_result()
        dup_result.single = AsyncMock(return_value=existing)

        session.run.side_effect = None
        session.run.return_value = dup_result
        result = await create_flag("c1", "spam", None, "user-fuid")
        assert result["success"] is False
        assert result["status"] == 409


class TestAdminMessageWorkflow:
    """Test admin message workflow: send -> inbox -> read -> reply."""

    async def test_full_message_flow(self, mock_all_drivers):
        from functions.messages import send_message, get_messages, get_message, reply_to_message, mark_message_read

        session, make_result = mock_all_drivers

        # Admin sends message
        session.run.return_value = make_result()
        result = await send_message("user-fuid", "Welcome", "Hello user!", "admin-fuid", "admin@test.com")
        assert result["success"] is True

        # User checks inbox
        from datetime import datetime, timezone
        record = MagicMock()
        record.__getitem__ = lambda self, k: {
            "uuid": "m1", "subject": "Welcome", "content": "Hello user!",
            "is_read": False, "created_at": datetime.now(timezone.utc),
            "sender_email": "admin@test.com",
        }[k]
        session.run.return_value = make_result([record])
        inbox = await get_messages("user-fuid")
        assert inbox["success"] is True
        assert len(inbox["data"]["messages"]) == 1
        assert inbox["data"]["messages"][0]["is_read"] is False

        # User marks as read
        read_record = MagicMock()
        read_record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        read_result = make_result()
        read_result.single = AsyncMock(return_value=read_record)
        session.run.return_value = read_result
        result = await mark_message_read("m1", "user-fuid")
        assert result["success"] is True

        # User replies
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"uuid": "m1"}[k]
        auth_result = make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        reply_result = make_result()

        session.run.side_effect = [auth_result, reply_result]
        result = await reply_to_message("m1", "Thanks admin!", "user-fuid", "user@test.com")
        assert result["success"] is True


class TestOwnerModeration:
    """Test ontology owner's moderation capabilities."""

    async def test_owner_can_delete_any_comment(self, mock_all_drivers):
        from functions.comments import delete_comment

        session, make_result = mock_all_drivers
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"authorized": True}[k]
        dep_record = MagicMock()
        dep_record.__getitem__ = lambda self, k: {"dep_count": 0}[k]

        auth_result = make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        dep_result = make_result()
        dep_result.single = AsyncMock(return_value=dep_record)
        delete_result = make_result()

        session.run.side_effect = [auth_result, dep_result, delete_result]
        result = await delete_comment("c1", "owner-fuid")
        assert result["success"] is True
        assert result["data"]["hard_deleted"] is True

    async def test_owner_can_remove_reaction(self, mock_all_drivers):
        from functions.reactions import remove_reaction_by_owner

        session, make_result = mock_all_drivers
        auth_record = MagicMock()
        auth_record.__getitem__ = lambda self, k: {"uuid": "r1"}[k]
        auth_result = make_result()
        auth_result.single = AsyncMock(return_value=auth_record)
        delete_result = make_result()

        session.run.side_effect = [auth_result, delete_result]
        result = await remove_reaction_by_owner("c1", "r1", "owner-fuid")
        assert result["success"] is True
