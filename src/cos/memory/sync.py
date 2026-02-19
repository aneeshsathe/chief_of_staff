"""iCloud path management and sync health for cross-device memory sharing."""

from __future__ import annotations

from pathlib import Path

import structlog

from cos.config.settings import DEFAULT_MEMORY_PATH

log = structlog.get_logger("memory.sync")


def get_memory_path(configured_path: Path | None = None) -> Path:
    """Resolve the memory data path, defaulting to iCloud."""
    path = configured_path or DEFAULT_MEMORY_PATH
    return path.expanduser()


def ensure_memory_path(configured_path: Path | None = None) -> Path:
    """Ensure the memory path exists and return it."""
    path = get_memory_path(configured_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def check_icloud_available() -> bool:
    """Check if iCloud Drive is available on this machine."""
    icloud_root = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"
    return icloud_root.exists()


def get_sync_status(configured_path: Path | None = None) -> dict[str, str | bool]:
    """Check sync status of the memory directory."""
    path = get_memory_path(configured_path)
    icloud_available = check_icloud_available()

    is_in_icloud = "Mobile Documents/com~apple~CloudDocs" in str(path)
    path_exists = path.exists()

    status = "healthy" if (path_exists and (not is_in_icloud or icloud_available)) else "unhealthy"

    return {
        "path": str(path),
        "exists": path_exists,
        "icloud_available": icloud_available,
        "is_icloud_path": is_in_icloud,
        "status": status,
    }
