"""
Handler migrated from get/energy.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_energy(format_type='table'):
    """
    Handler for energy

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
    
    # Filter energy-related entities
    energy_entities = []
    for state in states:
        entity_id = state.get('entity_id', '').lower()
        attrs = state.get('attributes', {})
        device_class = attrs.get('device_class', '').lower()
        
        # Check if entity is energy-related
        if (device_class in ['energy', 'power'] or 
            'energy' in entity_id or 
            'power' in entity_id or
            attrs.get('unit_of_measurement', '').lower() in ['kwh', 'wh', 'w', 'kw']):
            
            energy_data = {
                'entity_id': state.get('entity_id'),
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', state.get('entity_id')),
                'device_class': attrs.get('device_class'),
                'unit_of_measurement': attrs.get('unit_of_measurement'),
                'last_reset': attrs.get('last_reset'),
                'last_updated': state.get('last_updated')
            }
            energy_entities.append(energy_data)
    
    energy_entities.sort(key=lambda x: x['friendly_name'].lower())
    
    # Group by type (energy vs power)
    energy_sensors = [e for e in energy_entities if e.get('device_class') == 'energy' or 'energy' in e['entity_id'].lower()]
    power_sensors = [e for e in energy_entities if e.get('device_class') == 'power' or 'power' in e['entity_id'].lower()]
    
    result = {
        'total_energy_entities': len(energy_entities),
        'energy_sensors': len(energy_sensors),
        'power_sensors': len(power_sensors),
        'entities': energy_entities
    }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Energy Monitoring")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Energy Monitoring ===\n")
        click.echo(f"Total Energy Entities: {result['total_energy_entities']}\n")
        click.echo(f"Energy Sensors: {result['energy_sensors']}")
        click.echo(f"Power Sensors: {result['power_sensors']}\n")
        
        click.echo("## Energy Entities\n")
        for entity in energy_entities[:50]:
            click.echo(f"**{entity['friendly_name']}** (`{entity['entity_id']}`)")
            click.echo(f"  - State: {entity['state']}")
            if entity.get('device_class'):
                click.echo(f"  - Device Class: {entity['device_class']}")
            if entity.get('unit_of_measurement'):
                click.echo(f"  - Unit: {entity['unit_of_measurement']}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Energy Monitoring ===\n")
        click.echo(f"Total Energy Entities: {result['total_energy_entities']}\n")
        click.echo(f"Energy Sensors: {result['energy_sensors']} | Power Sensors: {result['power_sensors']}\n")
        click.echo(f"{'Entity ID':<50} {'State':<20} {'Device Class':<20} {'Unit':<15}")
        click.echo("-" * 105)
        
        for entity in energy_entities[:50]:
            entity_id = entity['entity_id']
            if len(entity_id) > 48:
                entity_id = entity_id[:45] + '...'
            device_class = entity.get('device_class') or '-'
            if len(device_class) > 18:
                device_class = device_class[:15] + '...'
            unit = entity.get('unit_of_measurement') or '-'
            if len(unit) > 13:
                unit = unit[:10] + '...'
            click.echo(f"{entity_id:<50} {entity['state']:<20} {device_class:<20} {unit:<15}")
        click.echo()


