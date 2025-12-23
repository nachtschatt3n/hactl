"""
Handler migrated from get/events.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_events(format_type='table'):
    """
    Handler for events

    Args:
        format_type: Output format
    """

    # Get format from command line
    # format_type passed as parameter
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Fetch available events
    url = f"{HASS_URL}/api/events"
    events = make_api_request(url, HASS_TOKEN)
    
    # Parse events
    event_list = []
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict):
                event_list.append({
                    'event': event.get('event', 'unknown'),
                    'listener_count': event.get('listener_count', 0)
                })
            elif isinstance(event, str):
                event_list.append({
                    'event': event,
                    'listener_count': 0
                })
    
    event_list.sort(key=lambda x: (-x['listener_count'], x['event']))
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(event_list, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Events")
        click.echo("---")
        click.echo(json_to_yaml(event_list))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Events ===\n")
        click.echo(f"Total Event Types: {len(event_list)}\n")
        
        # Group by listener count
        high_activity = [e for e in event_list if e['listener_count'] > 10]
        medium_activity = [e for e in event_list if 1 < e['listener_count'] <= 10]
        low_activity = [e for e in event_list if e['listener_count'] == 1]
        no_listeners = [e for e in event_list if e['listener_count'] == 0]
        
        if high_activity:
            click.echo(f"## High Activity Events ({len(high_activity)})\n")
            for event in high_activity:
                click.echo(f"**{event['event']}** - {event['listener_count']} listeners")
            click.echo()
        
        if medium_activity:
            click.echo(f"## Medium Activity Events ({len(medium_activity)})\n")
            for event in medium_activity:
                click.echo(f"**{event['event']}** - {event['listener_count']} listeners")
            click.echo()
        
        if low_activity:
            click.echo(f"## Low Activity Events ({len(low_activity)})\n")
            for event in low_activity[:20]:
                click.echo(f"**{event['event']}** - {event['listener_count']} listener")
            if len(low_activity) > 20:
                click.echo(f"... and {len(low_activity) - 20} more")
            click.echo()
        
        if no_listeners:
            click.echo(f"## Events with No Listeners ({len(no_listeners)})\n")
            for event in no_listeners[:20]:
                click.echo(f"**{event['event']}**")
            if len(no_listeners) > 20:
                click.echo(f"... and {len(no_listeners) - 20} more")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Events ===\n")
        click.echo(f"Total Event Types: {len(event_list)}\n")
        click.echo(f"{'Event Type':<50} {'Listeners':<10}")
        click.echo("-" * 60)
        
        for event in event_list:
            event_name = event['event']
            if len(event_name) > 48:
                event_name = event_name[:45] + '...'
            click.echo(f"{event_name:<50} {event['listener_count']:<10}")
        click.echo()


