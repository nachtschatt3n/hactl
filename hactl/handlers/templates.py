"""
Handler migrated from get/templates.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_templates(format_type='table'):
    """
    Handler for templates

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
    
    # Filter template entities
    templates = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('template.'):
            attrs = state.get('attributes', {})
            template_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'device_class': attrs.get('device_class'),
                'unit_of_measurement': attrs.get('unit_of_measurement'),
                'icon': attrs.get('icon'),
                'last_updated': state.get('last_updated')
            }
            templates.append(template_data)
    
    templates.sort(key=lambda x: x['friendly_name'].lower())
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(templates, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Template Entities")
        click.echo("---")
        click.echo(json_to_yaml(templates))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Template Entities ===\n")
        click.echo(f"Total Template Entities: {len(templates)}\n")
        
        for template in templates:
            click.echo(f"**{template['friendly_name']}** (`{template['entity_id']}`)")
            click.echo(f"  - State: {template['state']}")
            if template.get('device_class'):
                click.echo(f"  - Device Class: {template['device_class']}")
            if template.get('unit_of_measurement'):
                click.echo(f"  - Unit: {template['unit_of_measurement']}")
            if template.get('icon'):
                click.echo(f"  - Icon: {template['icon']}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Template Entities ===\n")
        click.echo(f"Total Template Entities: {len(templates)}\n")
        click.echo(f"{'Entity ID':<50} {'State':<20} {'Device Class':<20} {'Unit':<15}")
        click.echo("-" * 105)
        
        for template in templates:
            entity_id = template['entity_id']
            if len(entity_id) > 48:
                entity_id = entity_id[:45] + '...'
            device_class = template.get('device_class') or '-'
            if len(device_class) > 18:
                device_class = device_class[:15] + '...'
            unit = template.get('unit_of_measurement') or '-'
            if len(unit) > 13:
                unit = unit[:10] + '...'
            click.echo(f"{entity_id:<50} {template['state']:<20} {device_class:<20} {unit:<15}")
        click.echo()


