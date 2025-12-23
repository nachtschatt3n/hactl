"""
Handler migrated from get/persons_zones.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_persons_zones(format_type='table'):
    """
    Handler for persons_zones

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
    
    # Filter persons and zones
    persons = []
    zones = []
    
    for state in states:
        entity_id = state.get('entity_id', '')
        attrs = state.get('attributes', {})
        
        if entity_id.startswith('person.'):
            person_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'user_id': attrs.get('user_id'),
                'device_trackers': attrs.get('device_trackers', []),
                'latitude': attrs.get('latitude'),
                'longitude': attrs.get('longitude'),
                'gps_accuracy': attrs.get('gps_accuracy')
            }
            persons.append(person_data)
        elif entity_id.startswith('zone.'):
            zone_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'latitude': attrs.get('latitude'),
                'longitude': attrs.get('longitude'),
                'radius': attrs.get('radius'),
                'icon': attrs.get('icon'),
                'passive': attrs.get('passive', False)
            }
            zones.append(zone_data)
    
    persons.sort(key=lambda x: x['friendly_name'].lower())
    zones.sort(key=lambda x: x['friendly_name'].lower())
    
    result = {
        'persons': persons,
        'zones': zones
    }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Persons and Zones")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Persons and Zones ===\n")
        
        click.echo(f"## Persons ({len(persons)})\n")
        for person in persons:
            click.echo(f"**{person['friendly_name']}** (`{person['entity_id']}`)")
            click.echo(f"  - State: {person['state']}")
            if person.get('user_id'):
                click.echo(f"  - User ID: {person['user_id']}")
            if person.get('device_trackers'):
                click.echo(f"  - Device Trackers: {', '.join(person['device_trackers'])}")
            if person.get('latitude') and person.get('longitude'):
                click.echo(f"  - Location: {person['latitude']}, {person['longitude']}")
            click.echo()
        
        click.echo(f"## Zones ({len(zones)})\n")
        for zone in zones:
            click.echo(f"**{zone['friendly_name']}** (`{zone['entity_id']}`)")
            click.echo(f"  - State: {zone['state']}")
            if zone.get('latitude') and zone.get('longitude'):
                click.echo(f"  - Location: {zone['latitude']}, {zone['longitude']}")
            if zone.get('radius'):
                click.echo(f"  - Radius: {zone['radius']}m")
            if zone.get('icon'):
                click.echo(f"  - Icon: {zone['icon']}")
            if zone.get('passive'):
                click.echo(f"  - Passive: Yes")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Persons and Zones ===\n")
        
        click.echo(f"## Persons ({len(persons)})\n")
        click.echo(f"{'Name':<40} {'State':<20} {'Trackers':<30}")
        click.echo("-" * 90)
        for person in persons:
            name = person['friendly_name']
            if len(name) > 38:
                name = name[:35] + '...'
            trackers = ', '.join(person.get('device_trackers', [])) or '-'
            if len(trackers) > 28:
                trackers = trackers[:25] + '...'
            click.echo(f"{name:<40} {person['state']:<20} {trackers:<30}")
        click.echo()
        
        click.echo(f"## Zones ({len(zones)})\n")
        click.echo(f"{'Name':<40} {'Location':<30} {'Radius':<15}")
        click.echo("-" * 85)
        for zone in zones:
            name = zone['friendly_name']
            if len(name) > 38:
                name = name[:35] + '...'
            if zone.get('latitude') and zone.get('longitude'):
                location = f"{zone['latitude']:.4f}, {zone['longitude']:.4f}"
            else:
                location = '-'
            radius = f"{zone.get('radius', 0)}m" if zone.get('radius') else '-'
            click.echo(f"{name:<40} {location:<30} {radius:<15}")
        click.echo()


