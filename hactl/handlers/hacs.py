"""
Handler migrated from get/hacs.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml
from hactl.core.websocket import WebSocketClient

def get_hacs(format_type='table'):
    """
    Handler for hacs - List installed HACS repositories

    Args:
        format_type: Output format
    """

    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()

    # Try to get HACS repositories via WebSocket
    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    repositories = []

    try:
        ws.connect()

        # Get all HACS repositories
        try:
            all_repos = ws.call("hacs/repositories/list")
            if isinstance(all_repos, list):
                # Filter for only installed repositories
                repositories = [r for r in all_repos if r.get('installed', False)]
        except Exception as e:
            # HACS WebSocket API might not be available
            click.echo(f"Warning: Could not fetch HACS data: {e}", err=True)

    finally:
        ws.close()

    # Sort repositories by name
    if repositories:
        repositories = sorted(repositories, key=lambda x: x.get('name', ''))

    # Format output
    if format_type == 'json':
        click.echo(json.dumps(repositories, indent=2))
    elif format_type == 'yaml':
        click.echo("# HACS Installed Repositories")
        click.echo("---")
        click.echo(json_to_yaml(repositories))
    elif format_type == 'detail':
        click.echo("=== HACS Installed Repositories ===\n")
        click.echo(f"Total repositories: {len(repositories)}\n")

        if repositories:
            # Group by category if available
            by_category = {}
            for repo in repositories:
                if isinstance(repo, dict):
                    category = repo.get('category', 'unknown')
                    if category not in by_category:
                        by_category[category] = []
                    by_category[category].append(repo)

            for category, repos in sorted(by_category.items()):
                click.echo(f"\n**{category.upper()}** ({len(repos)} items)")
                click.echo("-" * 60)
                for repo in repos:
                    name = repo.get('name', repo.get('full_name', 'Unknown'))
                    click.echo(f"\n  {name}")
                    if repo.get('installed_version'):
                        click.echo(f"    Version: {repo['installed_version']}")
                    if repo.get('available_version') and repo.get('available_version') != repo.get('installed_version'):
                        click.secho(f"    Update available: {repo['available_version']}", fg='yellow')
                    if repo.get('authors'):
                        click.echo(f"    Authors: {', '.join(repo['authors'])}")
                    if repo.get('description'):
                        desc = repo['description']
                        if len(desc) > 100:
                            desc = desc[:97] + '...'
                        click.echo(f"    {desc}")
        else:
            click.echo("No HACS repositories found.")
            click.echo("Note: HACS data may not be accessible via API.")
        click.echo()
    else:  # table format
        click.echo("=== HACS Installed Repositories ===\n")

        if repositories:
            # Group by category
            by_category = {}
            for repo in repositories:
                if isinstance(repo, dict):
                    category = repo.get('category', 'unknown')
                    if category not in by_category:
                        by_category[category] = []
                    by_category[category].append(repo)

            click.echo(f"Total repositories: {len(repositories)}\n")

            for category, repos in sorted(by_category.items()):
                click.echo(f"\n{category.upper()} ({len(repos)})")
                click.echo(f"{'Name':<40} {'Version':<15} {'Status':<15}")
                click.echo("-" * 70)

                for repo in repos:
                    name = repo.get('name', repo.get('full_name', 'Unknown'))
                    if len(name) > 38:
                        name = name[:35] + '...'

                    version = repo.get('installed_version', '-')
                    if len(version) > 13:
                        version = version[:10] + '...'

                    status = 'OK'
                    if repo.get('available_version') and repo.get('available_version') != repo.get('installed_version'):
                        status = 'Update available'

                    click.echo(f"{name:<40} {version:<15} {status:<15}")
        else:
            click.echo("No HACS repositories found.")
            click.echo("\nNote: HACS data may not be accessible via API.")
            click.echo("Try using the HACS UI in Home Assistant for full details.")
        click.echo()


