"""
UPDATE command group for hactl
"""

import click


@click.group('update')
def update_group():
    """Update Home Assistant resources"""
    pass


@update_group.command('dashboard')
@click.argument('url_path')
@click.option('--from', 'from_file', required=True, type=click.Path(exists=True), help='YAML file to load')
@click.option('--create', is_flag=True, help='Create new dashboard (vs update existing)')
def update_dashboard(url_path, from_file, create):
    """Update or create a dashboard

    Examples:

    \b
        hactl update dashboard battery-monitor --from dashboard.yaml
        hactl update dashboard new-dash --from new.yaml --create
    """
    from hactl.handlers import dashboard_ops
    if create:
        dashboard_ops.create_dashboard(url_path, from_file)
    else:
        dashboard_ops.update_dashboard(url_path, from_file)


@update_group.command('helper')
@click.argument('helper_file', type=click.Path(exists=True))
@click.option('--check-only', is_flag=True, help='Only check if sensors exist')
def update_helper(helper_file, check_only):
    """Update helper sensors in configuration

    Examples:

    \b
        hactl update helper battery_summary.yaml
        hactl update helper battery_summary.yaml --check-only
    """
    from hactl.handlers import helper_ops
    helper_ops.update_helper(helper_file, check_only=check_only)
