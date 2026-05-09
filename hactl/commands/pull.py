"""
PULL command group for hactl

Pull live state from Home Assistant down to disk. Used as the recovery path
when ``hactl update dashboard`` blocks a push because of drift.
"""

import click


@click.group('pull')
def pull_group():
    """Pull live Home Assistant state to disk"""
    pass


@pull_group.command('dashboard')
@click.argument('url_path')
@click.option('--to', 'to_path', required=True, type=click.Path(), help='Path to write the live dashboard YAML to')
def pull_dashboard(url_path, to_path):
    """Fetch a live dashboard config and write it to disk.

    Examples:

    \b
        hactl pull dashboard battery-monitor --to generated/dashboards/battery-monitor.yaml
    """
    from hactl.handlers import dashboard_ops
    dashboard_ops.pull_dashboard(url_path, to_path)
