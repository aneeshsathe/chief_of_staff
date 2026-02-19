"""Human-in-the-loop approval hooks."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def require_approval(action: str, details: str = "", *, dry_run: bool = False) -> bool:
    """Prompt for human approval before taking an action.

    Returns True if approved, False if denied.
    In dry_run mode, always returns False and prints what would happen.
    """
    if dry_run:
        console.print(Panel(f"[dim]DRY RUN — would {action}[/dim]\n{details}", title="Dry Run"))
        return False

    console.print(
        Panel(f"[bold yellow]{action}[/bold yellow]\n{details}", title="Approval Required")
    )
    return typer.confirm("Proceed?", default=False)
