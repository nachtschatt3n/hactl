#!/usr/bin/env python3
"""
hactl - Home Assistant Control CLI

A kubectl-style command-line interface for Home Assistant.
"""

import click
from hactl import __version__


@click.group()
@click.version_option(version=__version__)
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--quiet', '-q', is_flag=True, help='Suppress non-error output')
@click.pass_context
def cli(ctx, verbose, quiet):
    """hactl - Home Assistant Control CLI

    A kubectl-style interface for managing Home Assistant via API.

    Examples:

    \b
        # Get resources
        hactl get devices --format json
        hactl get sensors battery
        hactl get dashboards

    \b
        # Update resources
        hactl update dashboard battery-monitor --from dashboard.yaml

    \b
        # Battery monitoring
        hactl battery list
        hactl battery monitor

    \b
        # Kubernetes operations
        hactl k8s update-config battery-summary.yaml

    \b
        # AI memory and generation
        hactl memory sync
        hactl generate dashboard "energy monitoring"
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet


# Register command groups
from hactl.commands import get_group, update_group, battery_group, k8s_group, memory_group, generate_group

cli.add_command(get_group)
cli.add_command(update_group)
cli.add_command(battery_group)
cli.add_command(k8s_group)
cli.add_command(memory_group)
cli.add_command(generate_group)


if __name__ == '__main__':
    cli()
