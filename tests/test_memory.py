"""Tests for memory sync utilities."""

from __future__ import annotations

from pathlib import Path

from cos.memory.sync import get_memory_path, check_icloud_available, get_sync_status
from cos.memory.datasets import ALL_DATASETS, EMAILS, MEETINGS


def test_all_datasets():
    assert EMAILS in ALL_DATASETS
    assert MEETINGS in ALL_DATASETS
    assert len(ALL_DATASETS) == 6


def test_get_memory_path_default():
    path = get_memory_path()
    assert "cos-data" in str(path)


def test_get_memory_path_custom(tmp_path: Path):
    path = get_memory_path(tmp_path / "custom")
    assert "custom" in str(path)


def test_get_sync_status(tmp_path: Path):
    status = get_sync_status(tmp_path)
    assert "path" in status
    assert "exists" in status
    assert "status" in status
