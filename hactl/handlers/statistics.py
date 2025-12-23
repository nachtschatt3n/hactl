"""
Handler migrated from get/statistics.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_statistics(format_type='table'):
    """
    Handler for statistics

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
    
    # Filter statistics entities
    statistics = []
    for state in states:
        entity_id = state.get('entity_id', '')
        attrs = state.get('attributes', {})
        
        # Check if entity has statistics attributes
        if (attrs.get('state_class') == 'measurement' or 
            attrs.get('state_class') == 'total' or
            attrs.get('device_class') in ['energy', 'power', 'temperature', 'humidity', 'pressure'] or
            'statistics' in entity_id.lower()):
            
            stat_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'device_class': attrs.get('device_class'),
                'state_class': attrs.get('state_class'),
                'unit_of_measurement': attrs.get('unit_of_measurement'),
                'last_reset': attrs.get('last_reset'),
                'last_updated': state.get('last_updated')
            }
            statistics.append(stat_data)
    
    statistics.sort(key=lambda x: x['friendly_name'].lower())
    
    # Group by device class
    by_device_class = {}
    for stat in statistics:
        device_class = stat.get('device_class') or 'unknown'
        if device_class not in by_device_class:
            by_device_class[device_class] = []
        by_device_class[device_class].append(stat)
    
    result = {
        'total_statistics': len(statistics),
        'by_device_class': {k: len(v) for k, v in by_device_class.items()},
        'statistics': statistics
    }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Statistics")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Statistics ===\n")
        click.echo(f"Total Statistics Entities: {result['total_statistics']}\n")
        
        click.echo("## Statistics by Device Class\n")
        for device_class, count in sorted(result['by_device_class'].items(), key=lambda x: -x[1]):
            click.echo(f"  {device_class}: {count} entities")
        click.echo()
        
        click.echo("## Statistics Entities\n")
        for stat in statistics[:50]:
            click.echo(f"**{stat['friendly_name']}** (`{stat['entity_id']}`)")
            click.echo(f"  - State: {stat['state']}")
            if stat.get('device_class'):
                click.echo(f"  - Device Class: {stat['device_class']}")
            if stat.get('state_class'):
                click.echo(f"  - State Class: {stat['state_class']}")
            if stat.get('unit_of_measurement'):
                click.echo(f"  - Unit: {stat['unit_of_measurement']}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Statistics ===\n")
        click.echo(f"Total Statistics Entities: {result['total_statistics']}\n")
        
        click.echo("## Statistics by Device Class\n")
        click.echo(f"{'Device Class':<30} {'Count':<15}")
        click.echo("-" * 45)
        for device_class, count in sorted(result['by_device_class'].items(), key=lambda x: -x[1]):
            click.echo(f"{device_class:<30} {count:<15}")
        click.echo()
        
        click.echo("## Statistics Entities\n")
        click.echo(f"{'Entity ID':<50} {'State':<20} {'Device Class':<20} {'Unit':<15}")
        click.echo("-" * 105)
        for stat in statistics[:50]:
            entity_id = stat['entity_id']
            if len(entity_id) > 48:
                entity_id = entity_id[:45] + '...'
            device_class = stat.get('device_class') or '-'
            if len(device_class) > 18:
                device_class = device_class[:15] + '...'
            unit = stat.get('unit_of_measurement') or '-'
            if len(unit) > 13:
                unit = unit[:10] + '...'
            click.echo(f"{entity_id:<50} {stat['state']:<20} {device_class:<20} {unit:<15}")
        click.echo()


