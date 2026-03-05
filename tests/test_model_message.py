import pytest
from functions.model_message import NewMessage, MessageReply, Message


class TestNewMessage:
    def test_valid_message(self):
        m = NewMessage(recipient_fuid="user-1", subject="Hello", content="How are you?")
        assert m.subject == "Hello"
        assert m.content == "How are you?"

    def test_subject_max_length(self):
        m = NewMessage(recipient_fuid="user-1", subject="a" * 200, content="body")
        assert len(m.subject) == 200

    def test_subject_over_max(self):
        with pytest.raises(Exception):
            NewMessage(recipient_fuid="user-1", subject="a" * 201, content="body")

    def test_body_max_length(self):
        m = NewMessage(recipient_fuid="user-1", subject="hi", content="a" * 5000)
        assert len(m.content) == 5000

    def test_body_over_max(self):
        with pytest.raises(Exception):
            NewMessage(recipient_fuid="user-1", subject="hi", content="a" * 5001)

    def test_blank_subject(self):
        with pytest.raises(Exception):
            NewMessage(recipient_fuid="user-1", subject="   ", content="body")

    def test_blank_content(self):
        with pytest.raises(Exception):
            NewMessage(recipient_fuid="user-1", subject="hi", content="   ")


class TestMessageReply:
    def test_valid_reply(self):
        r = MessageReply(content="Thanks!")
        assert r.content == "Thanks!"

    def test_blank_rejected(self):
        with pytest.raises(Exception):
            MessageReply(content="   ")

    def test_over_max(self):
        with pytest.raises(Exception):
            MessageReply(content="a" * 5001)


class TestMessage:
    def test_defaults(self):
        m = Message(subject="Hi", content="Hello")
        assert m.uuid
        assert m.is_read is False
        assert m.created_at is not None
