"""Tests for expanded caching system."""

import pytest
import time


def test_unread_cache_set_and_get():
    """Cache and retrieve unread count."""
    from functions.cache import cache_unread_count, get_cached_unread_count, invalidate_unread_cache
    invalidate_unread_cache()  # Clear first

    cache_unread_count("user-1", 5)
    assert get_cached_unread_count("user-1") == 5


def test_unread_cache_returns_none_on_miss():
    """Returns None when not cached."""
    from functions.cache import get_cached_unread_count, invalidate_unread_cache
    invalidate_unread_cache()

    assert get_cached_unread_count("nonexistent") is None


def test_invalidate_unread_cache_single_user():
    """Invalidating a single user's cache leaves others intact."""
    from functions.cache import cache_unread_count, get_cached_unread_count, invalidate_unread_cache
    invalidate_unread_cache()

    cache_unread_count("user-1", 5)
    cache_unread_count("user-2", 3)

    invalidate_unread_cache("user-1")
    assert get_cached_unread_count("user-1") is None
    assert get_cached_unread_count("user-2") == 3


def test_invalidate_unread_cache_all():
    """Invalidating all clears entire cache."""
    from functions.cache import cache_unread_count, get_cached_unread_count, invalidate_unread_cache

    cache_unread_count("user-1", 5)
    cache_unread_count("user-2", 3)

    invalidate_unread_cache()
    assert get_cached_unread_count("user-1") is None
    assert get_cached_unread_count("user-2") is None


def test_comments_cache_set_and_get():
    """Cache and retrieve comments."""
    from functions.cache import cache_comments, get_cached_comments, invalidate_comments_cache
    invalidate_comments_cache()

    data = {"comments": [{"uuid": "c1"}], "total": 1}
    cache_comments("ont-1", "0:20", data)
    assert get_cached_comments("ont-1", "0:20") == data


def test_invalidate_comments_cache_by_ontology():
    """Invalidate only specific ontology's comments."""
    from functions.cache import cache_comments, get_cached_comments, invalidate_comments_cache
    invalidate_comments_cache()

    cache_comments("ont-1", "0:20", {"a": 1})
    cache_comments("ont-2", "0:20", {"b": 2})

    invalidate_comments_cache("ont-1")
    assert get_cached_comments("ont-1", "0:20") is None
    assert get_cached_comments("ont-2", "0:20") == {"b": 2}


def test_activity_cache_set_and_get():
    """Cache and retrieve activity feed."""
    from functions.cache import cache_activity, get_cached_activity, invalidate_activity_cache
    invalidate_activity_cache()

    data = {"items": [{"id": "a1"}]}
    cache_activity("user-1", "0:20:None:None", data)
    assert get_cached_activity("user-1", "0:20:None:None") == data


def test_invalidate_activity_cache_by_user():
    """Invalidate only specific user's activity cache."""
    from functions.cache import cache_activity, get_cached_activity, invalidate_activity_cache
    invalidate_activity_cache()

    cache_activity("user-1", "0:20:None:None", {"a": 1})
    cache_activity("user-2", "0:20:None:None", {"b": 2})

    invalidate_activity_cache("user-1")
    assert get_cached_activity("user-1", "0:20:None:None") is None
    assert get_cached_activity("user-2", "0:20:None:None") == {"b": 2}
