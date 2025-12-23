"""
Sensor operations handler
"""

import json
import csv
import io
import click
from hactl.core import load_config, make_api_request


def get_sensors_by_type(sensor_type, format_type='table'):
    """
    Get sensors filtered by type.

    Args:
        sensor_type: Sensor type to filter (battery, co2, temperature, etc.)
        format_type: Output format (table, json, csv, list)
    """
    sensor_type = sensor_type.lower()

    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()

    # Fetch all states
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)

    # Filter sensors by type
    filtered = []
    for state in states:
        entity_id = state.get('entity_id', '').lower()
        attrs = state.get('attributes', {})
        device_class = attrs.get('device_class', '').lower()

        # Check if sensor matches type (by device_class or entity_id pattern)
        if (device_class == sensor_type) or (sensor_type in entity_id):
            filtered.append({
                'entity_id': state.get('entity_id'),
                'state': state.get('state', 'unknown'),
                'device_class': attrs.get('device_class', 'N/A'),
                'unit': attrs.get('unit_of_measurement', ''),
                'friendly_name': attrs.get('friendly_name', state.get('entity_id')),
                'last_updated': state.get('last_updated', '')
            })

    if not filtered:
        click.secho(f"No sensors found for type: {sensor_type}", fg='yellow', err=True)
        return

    click.secho(f"Found {len(filtered)} sensor(s)\n", fg='green', err=True)

    # Format output
    if format_type == 'json':
        click.echo(json.dumps(filtered, indent=2))
    elif format_type == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['entity_id', 'state', 'device_class', 'unit', 'friendly_name', 'last_updated'])
        for sensor in filtered:
            writer.writerow([
                sensor['entity_id'],
                sensor['state'],
                sensor['device_class'],
                sensor['unit'],
                sensor['friendly_name'],
                sensor['last_updated']
            ])
        click.echo(output.getvalue().rstrip())
    elif format_type == 'list':
        for sensor in filtered:
            click.echo(sensor['entity_id'])
    else:  # table format
        click.echo(f"{'ENTITY_ID':<50} {'STATE':<15} {'DEVICE_CLASS':<15} {'UNIT':<10} {'FRIENDLY_NAME':<30}")
        click.echo("-" * 120)
        for sensor in filtered:
            entity_id = sensor['entity_id']
            if len(entity_id) > 48:
                entity_id = entity_id[:45] + '...'
            friendly_name = sensor['friendly_name']
            if len(friendly_name) > 28:
                friendly_name = friendly_name[:25] + '...'
            click.echo(f"{entity_id:<50} {sensor['state']:<15} {sensor['device_class']:<15} {sensor['unit']:<10} {friendly_name:<30}")
