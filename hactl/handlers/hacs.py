"""
Handler migrated from get/hacs.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_hacs(format_type='table'):
    """
    Handler for hacs

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
    
    # Filter HACS-related entities
    hacs_entities = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if 'hacs' in entity_id.lower():
            attrs = state.get('attributes', {})
            hacs_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'device_class': attrs.get('device_class'),
                'unit_of_measurement': attrs.get('unit_of_measurement')
            }
            hacs_entities.append(hacs_data)
    
    hacs_entities.sort(key=lambda x: x['entity_id'])
    
    result = {
        'hacs_entities': hacs_entities,
        'note': 'HACS information may be limited via API. Check HACS UI for full details.'
    }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant HACS Information")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant HACS Information ===\n")
        click.echo(f"HACS-related Entities: {len(hacs_entities)}\n")
        
        if hacs_entities:
            for entity in hacs_entities:
                click.echo(f"**{entity['friendly_name']}** (`{entity['entity_id']}`)")
                click.echo(f"  - State: {entity['state']}")
                if entity.get('device_class'):
                    click.echo(f"  - Device Class: {entity['device_class']}")
                if entity.get('unit_of_measurement'):
                    click.echo(f"  - Unit: {entity['unit_of_measurement']}")
                click.echo()
        else:
            click.echo("No HACS-related entities found.")
            click.echo("Note: HACS information may not be exposed via the API.")
        click.echo()
    else:  # table format
        click.echo("=== Home Assistant HACS Information ===\n")
        click.echo(f"HACS-related Entities: {len(hacs_entities)}\n")
        
        if hacs_entities:
            click.echo(f"{'Entity ID':<50} {'State':<20} {'Device Class':<20}")
            click.echo("-" * 90)
            for entity in hacs_entities:
                entity_id = entity['entity_id']
                if len(entity_id) > 48:
                    entity_id = entity_id[:45] + '...'
                device_class = entity.get('device_class') or '-'
                if len(device_class) > 18:
                    device_class = device_class[:15] + '...'
                click.echo(f"{entity_id:<50} {entity['state']:<20} {device_class:<20}")
        else:
            click.echo("No HACS-related entities found.")
            click.echo("Note: HACS information may not be exposed via the API.")
        click.echo()


