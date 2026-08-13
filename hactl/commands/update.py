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
@click.option('--force', is_flag=True, help='Bypass the drift check and overwrite the live dashboard. A backup is still taken first.')
@click.option('--title', default=None, help='Sidebar title for a NEW dashboard (default: the config\'s title, else the url path). Ignored if it already exists.')
@click.option('--icon', default=None, help='Sidebar icon for a NEW dashboard, e.g. mdi:grill. Ignored if it already exists.')
@click.option('--no-sidebar', is_flag=True, help='Do not show a NEW dashboard in the sidebar.')
@click.option('--require-admin', is_flag=True, help='Restrict a NEW dashboard to admin users.')
def update_dashboard(url_path, from_file, create, force, title, icon, no_sidebar, require_admin):
    """Update or create a dashboard

    With --create the panel is registered in the sidebar first, then the
    config is saved. Re-running --create against an existing dashboard
    updates its config and leaves the registration untouched.

    Examples:

    \b
        hactl update dashboard battery-monitor --from dashboard.yaml
        hactl update dashboard new-dash --from new.yaml --create
        hactl update dashboard grill --from grill.yaml --create --title Grill --icon mdi:grill
        hactl update dashboard battery-monitor --from dashboard.yaml --force
    """
    from hactl.handlers import dashboard_ops
    if create:
        dashboard_ops.create_dashboard(
            url_path, from_file, force=force, title=title, icon=icon,
            show_in_sidebar=not no_sidebar, require_admin=require_admin,
        )
    else:
        dashboard_ops.update_dashboard(url_path, from_file, force=force)


@update_group.command('delete-dashboard')
@click.argument('url_path')
@click.option('--yes', is_flag=True, required=True, help='Confirm deletion (required).')
def delete_dashboard(url_path, yes):
    """Delete a dashboard's panel registration and its config

    Examples:

    \b
        hactl update delete-dashboard scratch-dash --yes
    """
    from hactl.handlers import dashboard_ops
    dashboard_ops.delete_dashboard(url_path)


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
