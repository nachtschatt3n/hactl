"""
Battery monitoring utilities handler
"""

import json
import click
from hactl.core import load_config, make_api_request


def list_batteries(format_type='table', exclude_mobile=True):
    """
    List all battery sensors.

    Args:
        format_type: Output format (table, json, list)
        exclude_mobile: If True, exclude mobile devices and cars
    """
    HASS_URL, HASS_TOKEN = load_config()

    # Get all states
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)

    # Filter battery sensors
    exclude_keywords = ['iphone', 'ipad', 'tablet', 'car', 'tesla', 'macbook', 'watch', 'android', 'state', 'tessy']

    battery_sensors = []
    for state in states:
        entity_id = state.get('entity_id', '').lower()

        # Must contain 'battery'
        if 'battery' not in entity_id:
            continue

        # Exclude mobile devices and cars
        if exclude_mobile and any(keyword in entity_id for keyword in exclude_keywords):
            continue

        # Include level sensors or direct battery sensors (but not state sensors)
        if 'level' in entity_id:
            battery_sensors.append({
                'entity_id': state.get('entity_id'),
                'friendly_name': state.get('attributes', {}).get('friendly_name', ''),
                'state': state.get('state', 'unknown'),
                'unit': state.get('attributes', {}).get('unit_of_measurement', '')
            })
        elif entity_id.endswith('_battery') and 'state' not in entity_id:
            battery_sensors.append({
                'entity_id': state.get('entity_id'),
                'friendly_name': state.get('attributes', {}).get('friendly_name', ''),
                'state': state.get('state', 'unknown'),
                'unit': state.get('attributes', {}).get('unit_of_measurement', '')
            })
        elif 'battery_percentage' in entity_id:
            battery_sensors.append({
                'entity_id': state.get('entity_id'),
                'friendly_name': state.get('attributes', {}).get('friendly_name', ''),
                'state': state.get('state', 'unknown'),
                'unit': state.get('attributes', {}).get('unit_of_measurement', '')
            })

    # Sort by entity_id
    battery_sensors.sort(key=lambda x: x['entity_id'])

    if format_type == 'json':
        click.echo(json.dumps(battery_sensors, indent=2))
    elif format_type == 'list':
        for sensor in battery_sensors:
            click.echo(sensor['entity_id'])
    else:  # table
        exclude_text = " (excluding mobile/car)" if exclude_mobile else ""
        click.secho(f"Found {len(battery_sensors)} device battery sensors{exclude_text}:\n", fg='green')
        for sensor in battery_sensors:
            name = sensor['friendly_name'] or sensor['entity_id']
            click.echo(f"  - {sensor['entity_id']}: {name} ({sensor['state']}{sensor['unit']})")


def check_sensors():
    """Check battery summary sensor availability"""
    HASS_URL, HASS_TOKEN = load_config()

    sensors = [
        'sensor.battery_summary_total',
        'sensor.battery_low_count',
        'sensor.battery_critical_count',
        'sensor.battery_average_level'
    ]

    click.echo("Battery Summary Sensors:")
    click.echo("=" * 50)

    all_available = True
    for sensor_id in sensors:
        url = f"{HASS_URL}/api/states/{sensor_id}"
        try:
            result = make_api_request(url, HASS_TOKEN)
            state = result.get('state', 'unknown')
            unit = result.get('attributes', {}).get('unit_of_measurement', '')

            if state == 'unavailable':
                click.secho(f"  ✗ {sensor_id}: {state} (unavailable)", fg='red')
                all_available = False
            else:
                click.secho(f"  ✓ {sensor_id}: {state} {unit}", fg='green')
        except Exception as e:
            click.secho(f"  ✗ {sensor_id}: ERROR - {str(e)[:60]}", fg='red')
            all_available = False

    click.echo()
    if all_available:
        click.secho("✓ All battery summary sensors are available", fg='green')
    else:
        click.secho("⚠ Some sensors are unavailable or missing", fg='yellow')


def create_monitor(dry_run=False):
    """
    Create battery monitoring dashboard and automations.

    Args:
        dry_run: If True, show what would be done without making changes
    """
    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made\n", fg='yellow')

    click.echo("Battery Monitor Setup")
    click.echo("=" * 50)
    click.echo("\nThis would create:")
    click.echo("  1. Battery summary template sensors")
    click.echo("  2. Battery monitoring dashboard")
    click.echo("  3. Low battery notification automation")
    click.echo()

    if dry_run:
        click.secho("✓ Dry run complete - no changes made", fg='green')
    else:
        click.echo("TODO: Implement battery monitor creation")
        click.secho("⚠ Not yet implemented", fg='yellow')
