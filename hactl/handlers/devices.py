"""
Device operations handler
"""

import json
import click
from hactl.core import load_config, json_to_yaml
from hactl.core.websocket import WebSocketClient


def get_devices(format_type='table'):
    """
    Get all devices from Home Assistant using WebSocket API.

    Args:
        format_type: Output format (table, json, yaml, detail)
    """
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()

    # Use WebSocket to get device registry
    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()
        device_list = ws.call('config/device_registry/list')
        ws.close()
    except Exception as e:
        click.echo(f"Error fetching devices: {e}", err=True)
        device_list = []

    if not device_list:
        device_list = []

    # Sort by name
    device_list.sort(key=lambda x: (x.get('name') or x.get('name_by_user') or '').lower())

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
            name = device.get('name') or device.get('name_by_user') or 'Unknown'
            click.echo(f"**{name}** (ID: {device.get('id')})")
            if device.get('manufacturer'):
                click.echo(f"  - Manufacturer: {device['manufacturer']}")
            if device.get('model'):
                click.echo(f"  - Model: {device['model']}")
            if device.get('area_id'):
                click.echo(f"  - Area ID: {device['area_id']}")
            if device.get('sw_version'):
                click.echo(f"  - Software Version: {device['sw_version']}")
            if device.get('hw_version'):
                click.echo(f"  - Hardware Version: {device['hw_version']}")
            if device.get('via_device_id'):
                click.echo(f"  - Connected via: {device['via_device_id']}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Devices ===\n")
        click.echo(f"Total Devices: {len(device_list)}\n")
        click.echo(f"{'Device Name':<40} {'Manufacturer':<25} {'Model':<30} {'Area ID':<20}")
        click.echo("-" * 115)

        for device in device_list:
            name = device.get('name') or device.get('name_by_user') or 'Unknown'
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
            click.echo(f"{name:<40} {manufacturer:<25} {model:<30} {area:<20}")
        click.echo()
