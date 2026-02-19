"""Cognee-based knowledge engine for memory management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from cos.core.errors import CosMemoryError

log = structlog.get_logger("memory.engine")


class MemoryEngine:
    """Wrapper around cognee for knowledge graph operations.

    Provides add/cognify/search/memify operations backed by
    SQLite + LanceDB (vector) + Kuzu (graph).
    """

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the cognee engine with the configured data path."""
        if self._initialized:
            return
        try:
            import cognee

            if self.data_path:
                self.data_path.mkdir(parents=True, exist_ok=True)
                cognee.config.data_root_directory(str(self.data_path / "data"))
                cognee.config.system_root_directory(str(self.data_path / "system"))

            self._initialized = True
            log.info("Memory engine initialized", data_path=str(self.data_path))
        except ImportError:
            raise CosMemoryError("cognee is not installed. Run: pip install cognee")
        except Exception as e:
            raise CosMemoryError(f"Failed to initialize memory engine: {e}") from e

    async def add(self, content: str, dataset: str = "default") -> None:
        """Add content to the knowledge base."""
        await self.initialize()
        try:
            import cognee

            await cognee.add(content, dataset_name=dataset)
            log.debug("Content added to memory", dataset=dataset, length=len(content))
        except Exception as e:
            raise CosMemoryError(f"Failed to add to memory: {e}") from e

    async def cognify(self) -> None:
        """Build/update the knowledge graph from added content."""
        await self.initialize()
        try:
            import cognee

            await cognee.cognify()
            log.info("Knowledge graph updated")
        except Exception as e:
            raise CosMemoryError(f"Failed to cognify: {e}") from e

    async def search(self, query: str, search_type: str = "INSIGHTS") -> list[dict[str, Any]]:
        """Search the knowledge base.

        search_type options: INSIGHTS, CHUNKS, GRAPH_COMPLETION, SUMMARIES
        """
        await self.initialize()
        try:
            import cognee
            from cognee.api.v1.search import SearchType

            st = getattr(SearchType, search_type, SearchType.INSIGHTS)
            results = await cognee.search(query_text=query, search_type=st)
            return [self._normalize_result(r) for r in results] if results else []
        except Exception as e:
            raise CosMemoryError(f"Memory search failed: {e}") from e

    async def memify(self) -> None:
        """Consolidate episodic memory patterns."""
        await self.initialize()
        try:
            import cognee

            await cognee.memify()
            log.info("Memory consolidated")
        except Exception as e:
            raise CosMemoryError(f"Failed to memify: {e}") from e

    async def reset(self) -> None:
        """Reset all memory data."""
        await self.initialize()
        try:
            import cognee

            await cognee.prune.prune_data()
            await cognee.prune.prune_system(metadata=True)
            log.info("Memory reset")
        except Exception as e:
            raise CosMemoryError(f"Failed to reset memory: {e}") from e

    @staticmethod
    def _normalize_result(result: Any) -> dict[str, Any]:
        """Normalize a cognee search result into a dict."""
        if isinstance(result, dict):
            return result
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if hasattr(result, "__dict__"):
            return result.__dict__
        return {"content": str(result)}
