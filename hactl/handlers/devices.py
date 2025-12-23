"""
Device operations handler
"""

import json
import click
from collections import defaultdict
from hactl.core import load_config, make_api_request, json_to_yaml


def get_devices(format_type='table'):
    """
    Get all devices from Home Assistant.

    Args:
        format_type: Output format (table, json, yaml, detail)
    """
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()

    # Fetch all states
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)

    # Group entities by device
    devices = defaultdict(lambda: {
        'device_id': None,
        'device_name': None,
        'manufacturer': None,
        'model': None,
        'area_id': None,
        'entities': [],
        'entity_count': 0
    })

    for state in states:
        attrs = state.get('attributes', {})
        device_id = attrs.get('device_id')
        if device_id:
            if devices[device_id]['device_id'] is None:
                devices[device_id]['device_id'] = device_id
                devices[device_id]['device_name'] = attrs.get('device_name') or attrs.get('friendly_name', '').split(' ')[0]
                devices[device_id]['manufacturer'] = attrs.get('manufacturer')
                devices[device_id]['model'] = attrs.get('model')
                devices[device_id]['area_id'] = attrs.get('area_id')

            devices[device_id]['entities'].append({
                'entity_id': state.get('entity_id'),
                'friendly_name': attrs.get('friendly_name'),
                'state': state.get('state')
            })
            devices[device_id]['entity_count'] = len(devices[device_id]['entities'])

    # Convert to list and sort
    device_list = []
    for device_id, device_info in devices.items():
        device_list.append(device_info)

    device_list.sort(key=lambda x: (x['device_name'] or '').lower())

    # Format output
    if format_type == 'json':
        click.echo(json.dumps(device_list, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Devices")
        click.echo("---")
        click.echo(json_to_yaml(device_list))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Devices ===\n")
        click.echo(f"Total Devices: {len(device_list)}\n")

        for device in device_list:
            click.echo(f"**{device['device_name'] or 'Unknown'}** (ID: {device['device_id']})")
            if device.get('manufacturer'):
                click.echo(f"  - Manufacturer: {device['manufacturer']}")
            if device.get('model'):
                click.echo(f"  - Model: {device['model']}")
            if device.get('area_id'):
                click.echo(f"  - Area: {device['area_id']}")
            click.echo(f"  - Entities: {device['entity_count']}")
            if device['entities']:
                click.echo("  - Entity List:")
                for entity in device['entities'][:5]:
                    click.echo(f"    - {entity['entity_id']} ({entity['friendly_name']})")
                if len(device['entities']) > 5:
                    click.echo(f"    ... and {len(device['entities']) - 5} more")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Devices ===\n")
        click.echo(f"Total Devices: {len(device_list)}\n")
        click.echo(f"{'Device Name':<40} {'Manufacturer':<25} {'Model':<30} {'Area':<20} {'Entities':<10}")
        click.echo("-" * 125)

        for device in device_list:
            name = device['device_name'] or 'Unknown'
            if len(name) > 38:
                name = name[:35] + '...'
            manufacturer = device.get('manufacturer') or '-'
            if len(manufacturer) > 23:
                manufacturer = manufacturer[:20] + '...'
            model = device.get('model') or '-'
            if len(model) > 28:
                model = model[:25] + '...'
            area = device.get('area_id') or '-'
            if len(area) > 18:
                area = area[:15] + '...'
            click.echo(f"{name:<40} {manufacturer:<25} {model:<30} {area:<20} {device['entity_count']:<10}")
        click.echo()
