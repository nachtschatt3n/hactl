"""
Handler migrated from get/home_structure.py
"""

import sys
import json
import click
from collections import defaultdict, Counter
from hactl.core import load_config, make_api_request, json_to_yaml

def get_home_structure(format_type='table'):
    """
    Handler for home_structure

    Args:
        format_type: Output format
    """

    # Get format from command line
    # format_type passed as parameter
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    click.echo("Analyzing Home Assistant home structure...", file=sys.stderr)
    click.echo("", file=sys.stderr)
    
    # Fetch all states
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)
    
    # Extract areas from area_id attributes
    areas_set = set()
    entities_by_area = defaultdict(list)
    
    for state in states:
        area_id = state.get('attributes', {}).get('area_id')
        if area_id:
            areas_set.add(area_id)
            entities_by_area[area_id].append(state)
    
    areas = sorted(areas_set)
    
    # Common room patterns
    room_patterns = [
        'living_room', 'kitchen', 'bedroom', 'bathroom', 'hallway', 'basement',
        'office', 'garage', 'attic', 'dining', 'laundry', 'pantry', 'closet',
        'entry', 'guest', 'kids', 'master', 'heater', 'toilet', 'stair',
        'upstairs', 'downstairs'
    ]
    
    # Count entities per room pattern
    room_counts = Counter()
    for state in states:
        entity_id = state.get('entity_id', '').lower()
        for pattern in room_patterns:
            if pattern in entity_id:
                room_counts[pattern] += 1
                break
    
    # Get devices with their areas
    devices_by_area = []
    for area_id in areas:
        entities = entities_by_area[area_id]
        sample_entities = [e.get('entity_id') for e in entities[:5]]
        devices_by_area.append({
            'area_id': area_id,
            'count': len(entities),
            'sample_entities': sample_entities
        })
    
    # Get room entities (unique room names found)
    room_entities = set()
    for state in states:
        entity_id = state.get('entity_id', '').lower()
        for pattern in room_patterns:
            if pattern in entity_id:
                room_entities.add(pattern)
    
    room_entities = sorted(room_entities)
    
    # Format room counts for output
    room_counts_list = [{'room': room, 'count': count} for room, count in sorted(room_counts.items(), key=lambda x: -x[1])]
    
    # Format output
    if format_type == 'json':
        result = {
            'areas': areas,
            'rooms_by_pattern': room_counts_list,
            'entities_by_room': list(room_entities),
            'devices_by_area': devices_by_area
        }
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'summary':
        click.echo("=== Home Structure Summary ===\n")
        
        click.echo("Areas (from area_id):")
        if areas:
            for area in areas:
                count = len(entities_by_area[area])
                click.echo(f"  - {area} ({count} entities)")
        else:
            click.echo("  (No areas found with area_id)")
        click.echo()
        
        click.echo("Rooms (from entity patterns):")
        for room_data in room_counts_list:
            click.echo(f"  - {room_data['room']}: {room_data['count']} entities")
    else:  # table format
        click.echo("=== Home Structure ===\n")
        
        click.echo("Areas (from area_id attributes):")
        if areas:
            for area in areas:
                entities = entities_by_area[area]
                count = len(entities)
                sample = ', '.join([e.get('entity_id') for e in entities[:3]])
                click.echo(f"  {area:<30} {count:3d} entities  (e.g., {sample})")
        else:
            click.echo("  (No areas found with area_id)")
        click.echo()
        
        click.echo("Rooms (detected from entity ID patterns):")
        for room_data in room_counts_list:
            click.echo(f"  {room_data['room']}: {room_data['count']} entities")
        click.echo()
        
        click.echo("Sample entities by room:")
        for room in room_entities[:10]:  # Limit to first 10 rooms
            matching_entities = [s for s in states if room in s.get('entity_id', '').lower()]
            click.echo(f"  {room}:")
            for entity in matching_entities[:5]:
                friendly_name = entity.get('attributes', {}).get('friendly_name', 'N/A')
                click.echo(f"    - {entity.get('entity_id')} ({friendly_name})")
            click.echo()


