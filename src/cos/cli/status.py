"""cos status command group."""

from __future__ import annotations

import anyio
import typer
from rich.console import Console

from cos.cli.formatters import print_health_table

status_app = typer.Typer(name="status", help="System status and diagnostics")
console = Console()


@status_app.command("health")
def health(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    """Check health of all integrations and memory."""
    anyio.run(_health_check, verbose)


async def _health_check(verbose: bool) -> None:
    from cos.config.settings import load_config
    from cos.core.logging import setup_logging

    setup_logging(verbose=verbose)
    config = load_config()

    checks: list[dict] = []

    # Check integrations
    from cos.integrations.registry import registry

    results = await registry.check_all()
    for r in results:
        checks.append({"name": r.name, "status": r.status.value, "message": r.message})

    # Check memory/sync
    from cos.memory.sync import get_sync_status

    sync = get_sync_status(config.sync.memory_path)
    checks.append(
        {
            "name": "memory_store",
            "status": "healthy" if sync["exists"] else "unconfigured",
            "message": f"Path: {sync['path']}" + (" (iCloud)" if sync["is_icloud_path"] else ""),
        }
    )

    if sync["is_icloud_path"]:
        checks.append(
            {
                "name": "icloud_sync",
                "status": "healthy" if sync["icloud_available"] else "unhealthy",
                "message": "iCloud Drive available"
                if sync["icloud_available"]
                else "iCloud Drive not found",
            }
        )

    # Check config
    from cos.config.settings import DEFAULT_CONFIG_PATH

    checks.append(
        {
            "name": "config",
            "status": "healthy" if DEFAULT_CONFIG_PATH.exists() else "unconfigured",
            "message": str(DEFAULT_CONFIG_PATH),
        }
    )

    print_health_table(checks)


@status_app.command("memory")
def memory() -> None:
    """Show memory store status."""
    from cos.config.settings import load_config
    from cos.memory.sync import get_sync_status

    config = load_config()
    sync = get_sync_status(config.sync.memory_path)

    console.print("\n[bold]Memory Store Status[/bold]")
    for key, value in sync.items():
        console.print(f"  {key}: {value}")
    console.print()
