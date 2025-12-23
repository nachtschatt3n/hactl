"""
BATTERY command group for hactl
"""

import click


@click.group('battery')
def battery_group():
    """Battery monitoring utilities"""
    pass


@battery_group.command('list')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'list']), default='table', help='Output format')
@click.option('--exclude-mobile/--include-mobile', default=True, help='Exclude mobile devices and cars')
def battery_list(format, exclude_mobile):
    """List all battery sensors

    Examples:

    \b
        hactl battery list
        hactl battery list --format json
        hactl battery list --include-mobile
    """
    from hactl.handlers import battery_monitor
    battery_monitor.list_batteries(format, exclude_mobile=exclude_mobile)


@battery_group.command('check')
def battery_check():
    """Check battery summary sensor availability

    Verifies that battery summary sensors exist and are reporting.

    Examples:

    \b
        hactl battery check
    """
    from hactl.handlers import battery_monitor
    battery_monitor.check_sensors()


@battery_group.command('monitor')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
def battery_monitor(dry_run):
    """Create battery monitoring dashboard and automations

    Examples:

    \b
        hactl battery monitor
        hactl battery monitor --dry-run
    """
    from hactl.handlers import battery_monitor
    battery_monitor.create_monitor(dry_run=dry_run)
