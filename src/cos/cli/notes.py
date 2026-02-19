"""cos notes command group."""

from __future__ import annotations

import anyio
import typer

from cos.cli.formatters import console, print_error, print_notes_list

notes_app = typer.Typer(name="notes", help="Apple Notes integration")


@notes_app.command("list")
def list_notes(
    folder: str = typer.Option(None, "--folder", "-f", help="Apple Notes folder"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """List notes from the Chief of Staff folder."""
    anyio.run(_list_notes, folder, verbose)


async def _list_notes(folder: str | None, verbose: bool) -> None:
    from cos.config.settings import load_config

    config = load_config()
    target_folder = folder or config.sync.apple_notes.folder

    try:
        from cos.integrations.apple_notes import AppleNotesClient

        client = AppleNotesClient(target_folder)
        notes = await client.list_notes()
        print_notes_list([n.model_dump() for n in notes])
    except Exception as e:
        print_error(f"Failed to read Apple Notes: {e}")
        if verbose:
            console.print_exception()


@notes_app.command("search")
def search(
    query: str = typer.Argument(..., help="Search query"),
    folder: str = typer.Option(None, "--folder", "-f"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Search notes by content."""
    anyio.run(_search_notes, query, folder, verbose)


async def _search_notes(query: str, folder: str | None, verbose: bool) -> None:
    from cos.config.settings import load_config

    config = load_config()
    target_folder = folder or config.sync.apple_notes.folder

    try:
        from cos.integrations.apple_notes import AppleNotesClient

        client = AppleNotesClient(target_folder)
        notes = await client.search_notes(query)
        print_notes_list([n.model_dump() for n in notes])
    except Exception as e:
        print_error(f"Search failed: {e}")
        if verbose:
            console.print_exception()
