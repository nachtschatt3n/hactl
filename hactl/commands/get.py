"""
GET command group for hactl
"""

import click


# Common format option decorator
def format_option(formats=None):
    """Decorator for standard format option"""
    if formats is None:
        formats = ['table', 'json', 'yaml', 'detail']

    def decorator(func):
        return click.option(
            '--format', '-f',
            type=click.Choice(formats),
            default='table',
            help='Output format'
        )(func)
    return decorator


@click.group('get')
def get_group():
    """Get resources from Home Assistant"""
    pass


@get_group.command('devices')
@format_option()
def get_devices(format):
    """Get all devices from Home Assistant

    Examples:

    \b
        hactl get devices
        hactl get devices --format json
        hactl get devices -f yaml
    """
    from hactl.handlers import devices
    devices.get_devices(format)


@get_group.command('states')
@format_option()
@click.option('--entity', '-e', help='Filter by entity ID pattern')
@click.option('--domain', '-d', help='Filter by domain (e.g., light, sensor)')
def get_states(format, entity, domain):
    """Get entity states

    Examples:

    \b
        hactl get states
        hactl get states --domain light
        hactl get states --entity "sensor.temperature*"
    """
    from hactl.handlers import states
    states.get_states(format, entity_filter=entity, domain_filter=domain)


@get_group.command('sensors')
@click.argument('sensor_type')
@format_option(['table', 'json', 'csv', 'list'])
def get_sensors(sensor_type, format):
    """Get sensors by type

    SENSOR_TYPE can be: battery, co2, temperature, humidity, etc.

    Examples:

    \b
        hactl get sensors battery
        hactl get sensors temperature --format json
        hactl get sensors co2 -f csv
    """
    from hactl.handlers import sensors
    sensors.get_sensors_by_type(sensor_type, format)


@get_group.command('integrations')
@format_option()
def get_integrations(format):
    """Get configured integrations

    Examples:

    \b
        hactl get integrations
        hactl get integrations --format json
    """
    from hactl.handlers import integrations
    integrations.get_integrations(format)


@get_group.command('services')
@format_option()
def get_services(format):
    """Get available services

    Examples:

    \b
        hactl get services
        hactl get services --format json
    """
    from hactl.handlers import services
    services.get_services(format)


@get_group.command('dashboards')
@format_option(['table', 'json', 'yaml', 'detail', 'yaml-save', 'yaml-single', 'validate'])
@click.option('--url-path', help='Dashboard or view path (e.g., "light-control" or "light-control/battery-monitor")')
@click.option('--output-dir', default='.', help='Output directory (for yaml-save)')
def get_dashboards(format, url_path, output_dir):
    """Get dashboard configurations

    Examples:

    \b
        hactl get dashboards
        hactl get dashboards --format yaml-save --output-dir dashboards/
        hactl get dashboards --format yaml-single --url-path light-control
        hactl get dashboards --format yaml-single --url-path light-control/battery-monitor
        hactl get dashboards --format validate --url-path light-control/battery-monitor
    """
    from hactl.handlers import dashboards
    dashboards.get_dashboards(format, url_path=url_path, output_dir=output_dir)


@get_group.command('automations')
@format_option()
def get_automations(format):
    """Get automations

    Examples:

    \b
        hactl get automations
        hactl get automations --format json
    """
    from hactl.handlers import automations_scripts_helpers
    automations_scripts_helpers.get_automations(format)


@get_group.command('scripts')
@format_option()
def get_scripts(format):
    """Get scripts

    Examples:

    \b
        hactl get scripts
        hactl get scripts --format json
    """
    from hactl.handlers import automations_scripts_helpers
    automations_scripts_helpers.get_scripts(format)


@get_group.command('helpers')
@format_option()
def get_helpers(format):
    """Get helper entities

    Examples:

    \b
        hactl get helpers
        hactl get helpers --format json
    """
    from hactl.handlers import automations_scripts_helpers
    automations_scripts_helpers.get_helpers(format)


@get_group.command('actions')
@format_option()
def get_actions(format):
    """Get action/script execution history"""
    from hactl.handlers import actions
    actions.get_actions(format)


@get_group.command('activity')
@format_option()
def get_activity(format):
    """Get recent activity and state changes"""
    from hactl.handlers import activity
    activity.get_activity(format)


@get_group.command('assist')
@format_option()
def get_assist(format):
    """Get Assist integration data"""
    from hactl.handlers import assist
    assist.get_assist(format)


@get_group.command('calendars')
@format_option()
def get_calendars(format):
    from hactl.handlers import calendars
    calendars.get_calendars(format)


@get_group.command('cameras')
@format_option()
def get_cameras(format):
    """Get camera entities"""
    from hactl.handlers import cameras
    cameras.get_cameras(format)


@get_group.command('energy')
@format_option()
def get_energy(format):
    """Get energy monitoring data"""
    from hactl.handlers import energy
    energy.get_energy(format)


@get_group.command('error-log')
@format_option()
def get_error_log(format):
    """Get error log entries"""
    from hactl.handlers import error_log
    error_log.get_error_log(format)


@get_group.command('events')
@format_option()
def get_events(format):
    """Get system event logs"""
    from hactl.handlers import events
    events.get_events(format)


@get_group.command('hacs')
@format_option()
def get_hacs(format):
    """Get HACS integration info"""
    from hactl.handlers import hacs
    hacs.get_hacs(format)


@get_group.command('history')
@format_option()
def get_history(format):
    """Get entity state history"""
    from hactl.handlers import history
    history.get_history(format)


@get_group.command('home-structure')
@format_option()
def get_home_structure(format):
    """Get home structure (areas, rooms)"""
    from hactl.handlers import home_structure
    home_structure.get_home_structure(format)


@get_group.command('media-players')
@format_option()
def get_media_players(format):
    """Get media player entities"""
    from hactl.handlers import media_players
    media_players.get_media_players(format)


@get_group.command('notifications')
@format_option()
def get_notifications(format):
    """Get notification entities"""
    from hactl.handlers import notifications
    notifications.get_notifications(format)


@get_group.command('persons-zones')
@format_option()
def get_persons_zones(format):
    """Get persons and zones

    Examples:

    \b
        hactl get persons-zones
        hactl get persons-zones --format json
    """
    from hactl.handlers import persons_zones
    persons_zones.get_persons_zones(format)


@get_group.command('scenes')
@format_option()
def get_scenes(format):
    """Get scene entities"""
    from hactl.handlers import scenes
    scenes.get_scenes(format)


@get_group.command('statistics')
@format_option()
def get_statistics(format):
    """Get statistics for entities"""
    from hactl.handlers import statistics
    statistics.get_statistics(format)


@get_group.command('templates')
@format_option()
def get_templates(format):
    """Get template entities"""
    from hactl.handlers import templates
    templates.get_templates(format)


@get_group.command('todos')
@format_option()
def get_todos(format):
    """Get todo list items"""
    from hactl.handlers import todos
    todos.get_todos(format)
