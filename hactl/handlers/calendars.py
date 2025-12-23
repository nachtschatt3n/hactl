"""
Handler migrated from get/calendars.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_calendars(format_type='table'):
    """
    Handler for calendars

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
    
    # Filter calendars
    calendars = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('calendar.'):
            attrs = state.get('attributes', {})
            calendar_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'message': attrs.get('message', ''),
                'all_day': attrs.get('all_day', False),
                'start_time': attrs.get('start_time'),
                'end_time': attrs.get('end_time'),
                'location': attrs.get('location', ''),
                'description': attrs.get('description', '')
            }
            calendars.append(calendar_data)
    
    calendars.sort(key=lambda x: x['friendly_name'].lower())
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(calendars, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Calendars")
        click.echo("---")
        click.echo(json_to_yaml(calendars))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Calendars ===\n")
        click.echo(f"Total Calendars: {len(calendars)}\n")
        
        for cal in calendars:
            click.echo(f"**{cal['friendly_name']}** (`{cal['entity_id']}`)")
            click.echo(f"  - State: {cal['state']}")
            if cal.get('message'):
                click.echo(f"  - Current Event: {cal['message']}")
            if cal.get('start_time'):
                click.echo(f"  - Start: {cal['start_time']}")
            if cal.get('end_time'):
                click.echo(f"  - End: {cal['end_time']}")
            if cal.get('location'):
                click.echo(f"  - Location: {cal['location']}")
            if cal.get('all_day'):
                click.echo(f"  - All Day: Yes")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Calendars ===\n")
        click.echo(f"Total Calendars: {len(calendars)}\n")
        click.echo(f"{'Calendar Name':<40} {'State':<20} {'Current Event':<40}")
        click.echo("-" * 100)
        
        for cal in calendars:
            name = cal['friendly_name']
            if len(name) > 38:
                name = name[:35] + '...'
            event = cal.get('message', '-') or '-'
            if len(event) > 38:
                event = event[:35] + '...'
            click.echo(f"{name:<40} {cal['state']:<20} {event:<40}")
        click.echo()


