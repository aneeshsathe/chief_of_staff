"""Tests for MemoryEngine (cognee wrapper)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cos.core.errors import CosMemoryError
from cos.memory.engine import MemoryEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cognee_mock() -> MagicMock:
    """Return a minimal mock that looks enough like the cognee package."""
    mock = MagicMock()
    mock.add = AsyncMock()
    mock.cognify = AsyncMock()
    mock.memify = AsyncMock()
    mock.prune = MagicMock()
    mock.prune.prune_data = AsyncMock()
    mock.prune.prune_system = AsyncMock()

    # cognee.search returns a list
    mock.search = AsyncMock(return_value=[])

    # cognee.api.v1.search.SearchType
    search_type_mock = MagicMock()
    search_type_mock.INSIGHTS = "INSIGHTS"
    search_type_mock.CHUNKS = "CHUNKS"

    # Patch config object
    mock.config = MagicMock()
    mock.config.data_root_directory = MagicMock()
    mock.config.system_root_directory = MagicMock()

    return mock, search_type_mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cognee_mock():
    """Inject a fake cognee module into sys.modules for the duration of a test."""
    mock_cognee, mock_search_type_mod = _make_cognee_mock()

    # Build fake submodule structure
    api_mod = ModuleType("cognee.api")
    v1_mod = ModuleType("cognee.api.v1")
    search_mod = ModuleType("cognee.api.v1.search")
    search_mod.SearchType = mock_search_type_mod

    with patch.dict(
        sys.modules,
        {
            "cognee": mock_cognee,
            "cognee.api": api_mod,
            "cognee.api.v1": v1_mod,
            "cognee.api.v1.search": search_mod,
        },
    ):
        yield mock_cognee, mock_search_type_mod


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestMemoryEngineInit:
    def test_default_data_path_is_none(self) -> None:
        engine = MemoryEngine()
        assert engine.data_path is None
        assert engine._initialized is False

    def test_custom_data_path_stored(self, tmp_path: Path) -> None:
        engine = MemoryEngine(data_path=tmp_path)
        assert engine.data_path == tmp_path

    @pytest.mark.asyncio
    async def test_initialize_sets_flag(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine()
        await engine.initialize()
        assert engine._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine()
        await engine.initialize()
        await engine.initialize()
        # config calls should only happen once (or zero if data_path is None)
        assert engine._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_with_data_path_creates_dir(self, cognee_mock, tmp_path: Path) -> None:
        mock_cognee, _ = cognee_mock
        data_dir = tmp_path / "memory"
        engine = MemoryEngine(data_path=data_dir)
        await engine.initialize()
        assert data_dir.exists()

    @pytest.mark.asyncio
    async def test_initialize_configures_cognee_paths(self, cognee_mock, tmp_path: Path) -> None:
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine(data_path=tmp_path)
        await engine.initialize()
        mock_cognee.config.data_root_directory.assert_called_once()
        mock_cognee.config.system_root_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_raises_when_cognee_missing(self) -> None:
        engine = MemoryEngine()
        with patch.dict(sys.modules, {"cognee": None}):
            with pytest.raises(CosMemoryError, match="cognee is not installed"):
                await engine.initialize()

    @pytest.mark.asyncio
    async def test_initialize_wraps_generic_exception(self) -> None:
        engine = MemoryEngine()
        bad_mod = MagicMock()
        bad_mod.config.data_root_directory.side_effect = RuntimeError("boom")
        # Give it a data_path so config calls happen
        engine.data_path = Path("/some/path")
        with patch.dict(sys.modules, {"cognee": bad_mod}):
            with pytest.raises(CosMemoryError, match="Failed to initialize"):
                await engine.initialize()


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


class TestMemoryEngineAdd:
    @pytest.mark.asyncio
    async def test_add_calls_cognee_add(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine()
        await engine.add("hello world", dataset="test")
        mock_cognee.add.assert_awaited_once_with("hello world", dataset_name="test")

    @pytest.mark.asyncio
    async def test_add_default_dataset(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine()
        await engine.add("content")
        _, kwargs = mock_cognee.add.call_args
        assert kwargs["dataset_name"] == "default"

    @pytest.mark.asyncio
    async def test_add_wraps_exception(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        mock_cognee.add.side_effect = RuntimeError("db error")
        engine = MemoryEngine()
        with pytest.raises(CosMemoryError, match="Failed to add to memory"):
            await engine.add("content")


# ---------------------------------------------------------------------------
# cognify
# ---------------------------------------------------------------------------


class TestMemoryEngineCognify:
    @pytest.mark.asyncio
    async def test_cognify_calls_cognee(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine()
        await engine.cognify()
        mock_cognee.cognify.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cognify_wraps_exception(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        mock_cognee.cognify.side_effect = RuntimeError("graph error")
        engine = MemoryEngine()
        with pytest.raises(CosMemoryError, match="Failed to cognify"):
            await engine.cognify()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestMemoryEngineSearch:
    @pytest.mark.asyncio
    async def test_search_returns_empty_list_on_no_results(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        mock_cognee.search.return_value = []
        engine = MemoryEngine()
        results = await engine.search("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_normalizes_dict_results(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        mock_cognee.search.return_value = [{"text": "fact 1"}, {"text": "fact 2"}]
        engine = MemoryEngine()
        results = await engine.search("query")
        assert len(results) == 2
        assert results[0] == {"text": "fact 1"}

    @pytest.mark.asyncio
    async def test_search_normalizes_model_dump_results(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        obj = MagicMock()
        obj.model_dump.return_value = {"content": "some insight"}
        # Remove __dict__ attribute so model_dump path is taken
        del obj.__dict__
        mock_cognee.search.return_value = [obj]
        engine = MemoryEngine()
        results = await engine.search("query")
        assert results[0] == {"content": "some insight"}

    @pytest.mark.asyncio
    async def test_search_wraps_exception(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        mock_cognee.search.side_effect = RuntimeError("search error")
        engine = MemoryEngine()
        with pytest.raises(CosMemoryError, match="Memory search failed"):
            await engine.search("query")


# ---------------------------------------------------------------------------
# memify
# ---------------------------------------------------------------------------


class TestMemoryEngineMemify:
    @pytest.mark.asyncio
    async def test_memify_calls_cognee(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine()
        await engine.memify()
        mock_cognee.memify.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_memify_wraps_exception(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        mock_cognee.memify.side_effect = RuntimeError("memify error")
        engine = MemoryEngine()
        with pytest.raises(CosMemoryError, match="Failed to memify"):
            await engine.memify()


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestMemoryEngineReset:
    @pytest.mark.asyncio
    async def test_reset_calls_prune_data_and_system(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine()
        await engine.reset()
        mock_cognee.prune.prune_data.assert_awaited_once()
        mock_cognee.prune.prune_system.assert_awaited_once_with(metadata=True)

    @pytest.mark.asyncio
    async def test_reset_wraps_exception(self, cognee_mock) -> None:
        mock_cognee, _ = cognee_mock
        mock_cognee.prune.prune_data.side_effect = RuntimeError("prune error")
        engine = MemoryEngine()
        with pytest.raises(CosMemoryError, match="Failed to reset memory"):
            await engine.reset()


# ---------------------------------------------------------------------------
# _normalize_result
# ---------------------------------------------------------------------------


class TestNormalizeResult:
    def test_dict_passthrough(self) -> None:
        d = {"a": 1}
        assert MemoryEngine._normalize_result(d) == d

    def test_model_dump_used(self) -> None:
        obj = MagicMock(spec=["model_dump"])
        obj.model_dump.return_value = {"key": "val"}
        assert MemoryEngine._normalize_result(obj) == {"key": "val"}

    def test_dict_attr_used(self) -> None:
        class Obj:
            def __init__(self):
                self.x = 42

        result = MemoryEngine._normalize_result(Obj())
        assert result["x"] == 42

    def test_fallback_to_str(self) -> None:
        result = MemoryEngine._normalize_result(42)
        assert result == {"content": "42"}
