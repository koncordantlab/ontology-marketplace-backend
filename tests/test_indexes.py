"""Tests for performance index migration file."""

import os
import pytest


def test_index_migration_file_exists():
    """The performance index migration file exists."""
    path = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'add_performance_indexes.cql')
    assert os.path.isfile(path), "Migration file missing"


def test_index_migration_contains_required_indexes():
    """The migration file contains all required indexes."""
    path = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'add_performance_indexes.cql')
    with open(path) as f:
        content = f.read()

    required_indexes = [
        ('User', 'fuid'),
        ('Ontology', 'uuid'),
        ('Comment', 'created_at'),
        ('Tag', 'name'),
    ]

    for label, prop in required_indexes:
        assert f'({label[0].lower()}:{label})' in content or f'(:{label})' in content, \
            f"Missing index for {label}.{prop}"
        assert 'IF NOT EXISTS' in content, "Missing IF NOT EXISTS clause"
