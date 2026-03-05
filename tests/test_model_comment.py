import pytest
from functions.model_comment import NewComment, Comment, NewReaction, NewReply, VALID_EMOJIS


class TestNewComment:
    def test_valid_comment(self):
        c = NewComment(content="This is a valid comment")
        assert c.content == "This is a valid comment"

    def test_strips_whitespace(self):
        c = NewComment(content="  hello  ")
        assert c.content == "hello"

    def test_empty_string_rejected(self):
        with pytest.raises(Exception):
            NewComment(content="")

    def test_blank_string_rejected(self):
        with pytest.raises(Exception):
            NewComment(content="   ")

    def test_max_length_ok(self):
        c = NewComment(content="a" * 2000)
        assert len(c.content) == 2000

    def test_over_max_length_rejected(self):
        with pytest.raises(Exception):
            NewComment(content="a" * 2001)


class TestComment:
    def test_defaults(self):
        c = Comment(content="test")
        assert c.uuid
        assert c.content == "test"
        assert c.is_deleted is False
        assert c.created_at is not None
        assert c.updated_at is None
        assert c.reply_count == 0
        assert c.reactions == {}
        assert c.is_editable is False

    def test_from_new_comment(self):
        nc = NewComment(content="hello world")
        c = Comment.from_new_comment(nc, author_email="user@test.com")
        assert c.content == "hello world"
        assert c.author_email == "user@test.com"


class TestNewReaction:
    def test_valid_emojis(self):
        for emoji in VALID_EMOJIS:
            r = NewReaction(emoji=emoji)
            assert r.emoji == emoji

    def test_invalid_emoji_rejected(self):
        with pytest.raises(Exception):
            NewReaction(emoji="🤔")

    def test_text_rejected(self):
        with pytest.raises(Exception):
            NewReaction(emoji="like")


class TestNewReply:
    def test_valid_reply(self):
        r = NewReply(content="This is a reply")
        assert r.content == "This is a reply"

    def test_empty_rejected(self):
        with pytest.raises(Exception):
            NewReply(content="")

    def test_over_max_length_rejected(self):
        with pytest.raises(Exception):
            NewReply(content="a" * 2001)
