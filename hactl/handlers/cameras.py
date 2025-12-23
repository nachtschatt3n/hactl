"""
Handler migrated from get/cameras.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_cameras(format_type='table'):
    """
    Handler for cameras

    Args:
        format_type: Output format
    """

    # Get format from command line
    # format_type passed as parameter
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Fetch all states
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)
    
    # Filter cameras
    cameras = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('camera.'):
            attrs = state.get('attributes', {})
            camera_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'device_class': attrs.get('device_class'),
                'model': attrs.get('model'),
                'brand': attrs.get('brand'),
                'supported_features': attrs.get('supported_features', 0),
                'access_token': 'present' if attrs.get('access_token') else 'none',
                'entity_picture': attrs.get('entity_picture')
            }
            cameras.append(camera_data)
    
    cameras.sort(key=lambda x: x['friendly_name'].lower())
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(cameras, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Cameras")
        click.echo("---")
        click.echo(json_to_yaml(cameras))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Cameras ===\n")
        click.echo(f"Total Cameras: {len(cameras)}\n")
        
        for camera in cameras:
            click.echo(f"**{camera['friendly_name']}** (`{camera['entity_id']}`)")
            click.echo(f"  - State: {camera['state']}")
            if camera.get('brand'):
                click.echo(f"  - Brand: {camera['brand']}")
            if camera.get('model'):
                click.echo(f"  - Model: {camera['model']}")
            if camera.get('device_class'):
                click.echo(f"  - Device Class: {camera['device_class']}")
            click.echo(f"  - Access Token: {camera['access_token']}")
            if camera.get('entity_picture'):
                click.echo(f"  - Picture URL: {camera['entity_picture']}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Cameras ===\n")
        click.echo(f"Total Cameras: {len(cameras)}\n")
        click.echo(f"{'Camera Name':<40} {'State':<20} {'Brand':<20} {'Model':<30}")
        click.echo("-" * 110)
        
        for camera in cameras:
            name = camera['friendly_name']
            if len(name) > 38:
                name = name[:35] + '...'
            brand = camera.get('brand') or '-'
            if len(brand) > 18:
                brand = brand[:15] + '...'
            model = camera.get('model') or '-'
            if len(model) > 28:
                model = model[:25] + '...'
            click.echo(f"{name:<40} {camera['state']:<20} {brand:<20} {model:<30}")
        click.echo()


