"""cos config command group."""

from __future__ import annotations

import typer
import yaml
from rich.console import Console
from rich.syntax import Syntax

from cos.cli.formatters import print_error, print_success

config_app = typer.Typer(name="config", help="Configuration management")
console = Console()


@config_app.command("init")
def init(
    account_id: str = typer.Option("default", "--account", "-a", help="Account ID for OAuth"),
) -> None:
    """Initialize cos configuration and run OAuth flow."""
    from cos.config.settings import COS_DIR, DEFAULT_CONFIG_PATH, AppConfig, save_config

    # Ensure config directory
    COS_DIR.mkdir(parents=True, exist_ok=True)

    # Create default config if none exists
    if not DEFAULT_CONFIG_PATH.exists():
        from cos.config.settings import CalendarConfig, ContextConfig, EmailAccountConfig

        config = AppConfig(
            active_context="day_job",
            contexts={
                "day_job": ContextConfig(
                    label="Day Job",
                    email_accounts=[EmailAccountConfig(id=account_id, type="google")],
                    calendars=[CalendarConfig(id="work_cal", type="google")],
                ),
            },
        )
        save_config(config)
        print_success(f"Created config at {DEFAULT_CONFIG_PATH}")
    else:
        print_success(f"Config already exists at {DEFAULT_CONFIG_PATH}")

    # Run OAuth flow
    console.print("\n[bold]Google OAuth Setup[/bold]")
    console.print(f"Looking for client_secret.json in {COS_DIR}/")

    from cos.integrations.google.auth import CLIENT_SECRETS_PATH, has_credentials, run_oauth_flow

    if has_credentials(account_id):
        print_success(f"Credentials already stored for account '{account_id}'")
        if not typer.confirm("Re-authenticate?", default=False):
            return

    if not CLIENT_SECRETS_PATH.exists():
        print_error(
            f"Client secrets file not found at {CLIENT_SECRETS_PATH}\n"
            "Download it from Google Cloud Console:\n"
            "1. Go to console.cloud.google.com > APIs & Services > Credentials\n"
            "2. Create OAuth 2.0 Client ID (Desktop app)\n"
            "3. Download JSON and save as client_secret.json in ~/.cos/"
        )
        raise typer.Exit(1)

    try:
        run_oauth_flow(account_id)
        print_success(f"Authenticated account '{account_id}' and stored credentials in keychain")
    except Exception as e:
        print_error(f"OAuth flow failed: {e}")
        raise typer.Exit(1)


@config_app.command("show")
def show() -> None:
    """Show current configuration."""
    from cos.config.settings import DEFAULT_CONFIG_PATH, load_config

    config = load_config()
    data = config.model_dump(mode="json")

    console.print(f"\n[bold]Config file:[/bold] {DEFAULT_CONFIG_PATH}")
    console.print(Syntax(yaml.dump(data, default_flow_style=False), "yaml", theme="monokai"))


@config_app.command("contexts")
def contexts() -> None:
    """List all configured contexts."""
    from cos.config.contexts import list_contexts
    from cos.config.settings import load_config

    config = load_config()
    ctx_list = list_contexts(config)

    if not ctx_list:
        console.print("[dim]No contexts configured. Run 'cos config init' first.[/dim]")
        return

    for name, label, is_active in ctx_list:
        marker = " [green](active)[/green]" if is_active else ""
        console.print(f"  [bold]{name}[/bold]: {label}{marker}")


@config_app.command("test")
def test() -> None:
    """Test all configured integrations."""
    import anyio

    anyio.run(_test_integrations)


async def _test_integrations() -> None:
    from cos.integrations.registry import registry

    results = await registry.check_all()
    if not results:
        console.print("[dim]No integrations registered. Run 'cos config init' first.[/dim]")
        return

    from cos.cli.formatters import print_health_table

    print_health_table(
        [{"name": r.name, "status": r.status.value, "message": r.message} for r in results]
    )
