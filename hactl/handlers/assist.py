"""
Handler migrated from get/assist.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_assist(format_type='table'):
    """
    Handler for assist

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
    
    # Filter assist-related entities
    assist_entities = []
    for state in states:
        entity_id = state.get('entity_id', '').lower()
        if 'assist' in entity_id:
            attrs = state.get('attributes', {})
            assist_data = {
                'entity_id': state.get('entity_id'),
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', state.get('entity_id')),
                'device_class': attrs.get('device_class'),
                'last_updated': state.get('last_updated')
            }
            assist_entities.append(assist_data)
    
    assist_entities.sort(key=lambda x: x['entity_id'])
    
    result = {
        'assist_entities': assist_entities,
        'note': 'Assist pipeline information may require WebSocket API access for full details'
    }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Assist Configuration")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Assist Configuration ===\n")
        click.echo(f"Assist-related Entities: {len(assist_entities)}\n")
        
        if assist_entities:
            for entity in assist_entities:
                click.echo(f"**{entity['friendly_name']}** (`{entity['entity_id']}`)")
                click.echo(f"  - State: {entity['state']}")
                if entity.get('device_class'):
                    click.echo(f"  - Device Class: {entity['device_class']}")
                click.echo()
        else:
            click.echo("No Assist-related entities found.")
            click.echo("Note: Assist information may not be exposed via the REST API.")
        click.echo()
    else:  # table format
        click.echo("=== Home Assistant Assist Configuration ===\n")
        click.echo(f"Assist-related Entities: {len(assist_entities)}\n")
        
        if assist_entities:
            click.echo(f"{'Entity ID':<50} {'State':<20} {'Device Class':<20}")
            click.echo("-" * 90)
            for entity in assist_entities:
                entity_id = entity['entity_id']
                if len(entity_id) > 48:
                    entity_id = entity_id[:45] + '...'
                device_class = entity.get('device_class') or '-'
                if len(device_class) > 18:
                    device_class = device_class[:15] + '...'
                click.echo(f"{entity_id:<50} {entity['state']:<20} {device_class:<20}")
        else:
            click.echo("No Assist-related entities found.")
            click.echo("Note: Assist information may not be exposed via the REST API.")
        click.echo()


