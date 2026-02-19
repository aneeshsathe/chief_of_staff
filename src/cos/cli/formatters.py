"""Rich output formatters for CLI display."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def print_briefing(
    content: str, *, context: str = "", cost_usd: float = 0.0, tokens: int = 0
) -> None:
    """Print a formatted briefing with Rich."""
    header = "Morning Briefing"
    if context:
        header += f" — {context}"

    console.print()
    console.print(Panel(Markdown(content), title=header, border_style="blue", padding=(1, 2)))

    if cost_usd > 0 or tokens > 0:
        footer = Text()
        if tokens > 0:
            footer.append(f"Tokens: {tokens:,}", style="dim")
        if cost_usd > 0:
            if tokens > 0:
                footer.append(" | ", style="dim")
            footer.append(f"Cost: ${cost_usd:.4f}", style="dim")
        console.print(footer)
    console.print()


def print_health_table(checks: list[dict]) -> None:
    """Print a health check table."""
    table = Table(title="Integration Health", show_header=True, header_style="bold")
    table.add_column("Service", style="bold")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    status_styles = {
        "healthy": "[green]healthy[/green]",
        "degraded": "[yellow]degraded[/yellow]",
        "unhealthy": "[red]unhealthy[/red]",
        "unconfigured": "[dim]unconfigured[/dim]",
    }

    for check in checks:
        status = check.get("status", "unknown")
        styled_status = status_styles.get(status, status)
        table.add_row(check.get("name", ""), styled_status, check.get("message", ""))

    console.print()
    console.print(table)
    console.print()


def print_notes_list(notes: list[dict]) -> None:
    """Print a formatted list of notes."""
    if not notes:
        console.print("[dim]No notes found.[/dim]")
        return

    table = Table(title="Apple Notes", show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold")
    table.add_column("Modified", style="dim")
    table.add_column("Preview", max_width=60)

    for i, note in enumerate(notes, 1):
        modified = note.get("modified", "")
        if modified:
            modified = str(modified)[:16]
        preview = note.get("body", "")[:80].replace("\n", " ")
        table.add_row(str(i), note.get("title", "Untitled"), modified, preview)

    console.print()
    console.print(table)
    console.print()


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]OK:[/bold green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")
