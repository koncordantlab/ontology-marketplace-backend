import pytest
from functions.model_flag import NewFlag, Flag, VALID_REASONS


class TestNewFlag:
    def test_valid_reasons(self):
        for reason in VALID_REASONS:
            if reason == "other":
                f = NewFlag(reason=reason, details="some details")
            else:
                f = NewFlag(reason=reason)
            assert f.reason == reason

    def test_invalid_reason(self):
        with pytest.raises(Exception):
            NewFlag(reason="invalid_reason")

    def test_other_requires_details(self):
        with pytest.raises(Exception):
            NewFlag(reason="other")

    def test_other_with_blank_details(self):
        with pytest.raises(Exception):
            NewFlag(reason="other", details="   ")

    def test_other_with_valid_details(self):
        f = NewFlag(reason="other", details="This is problematic because...")
        assert f.details == "This is problematic because..."

    def test_details_max_length(self):
        with pytest.raises(Exception):
            NewFlag(reason="other", details="a" * 501)

    def test_details_at_max_length(self):
        f = NewFlag(reason="other", details="a" * 500)
        assert len(f.details) == 500


class TestFlag:
    def test_defaults(self):
        f = Flag(reason="spam")
        assert f.uuid
        assert f.status == "pending"
        assert f.created_at is not None
        assert f.reviewed_at is None
