"""Root Typer application for cos CLI."""

from __future__ import annotations

import typer

from cos.cli.briefing import briefing_app
from cos.cli.config_cmd import config_app
from cos.cli.notes import notes_app
from cos.cli.status import status_app

app = typer.Typer(
    name="cos",
    help="AI Chief of Staff - your morning briefing, triage, and task management agent.",
    no_args_is_help=True,
)

app.add_typer(briefing_app)
app.add_typer(config_app)
app.add_typer(notes_app)
app.add_typer(status_app)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """AI Chief of Staff CLI."""
    if verbose:
        from cos.core.logging import setup_logging

        setup_logging(verbose=True)
