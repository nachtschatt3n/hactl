"""
Handler migrated from get/error_log.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_error_log(format_type='table'):
    """
    Handler for error_log

    Args:
        format_type: Output format
    """

    # Get format from command line
    # format_type passed as parameter
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Fetch all states to find unavailable entities
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)
    
    # Find unavailable entities
    unavailable = []
    for state in states:
        if state.get('state') == 'unavailable':
            attrs = state.get('attributes', {})
            unavailable.append({
                'entity_id': state.get('entity_id'),
                'friendly_name': attrs.get('friendly_name', state.get('entity_id')),
                'last_updated': state.get('last_updated')
            })
    
    unavailable.sort(key=lambda x: x['entity_id'])
    
    # Try to fetch logbook for errors
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    logbook_url = f"{HASS_URL}/api/logbook/{start_time.isoformat()}"
    
    logbook_entries = []
    try:
        logbook_data = make_api_request(logbook_url, HASS_TOKEN)
        if isinstance(logbook_data, list) and len(logbook_data) > 0:
            # Filter for error-like entries
            for entry in logbook_data:
                if isinstance(entry, dict):
                    name = entry.get('name', '')
                    if any(keyword in name.lower() for keyword in ['error', 'failed', 'unavailable', 'exception']):
                        logbook_entries.append(entry)
    except Exception:
        # Logbook might not be available or have errors
        pass
    
    result = {
        'unavailable_entities': unavailable,
        'recent_errors': logbook_entries[:50]  # Limit to 50 most recent
    }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Error Log")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Error Log ===\n")
        
        click.echo(f"## Unavailable Entities ({len(unavailable)})\n")
        for entity in unavailable:
            click.echo(f"**{entity['friendly_name']}** (`{entity['entity_id']}`)")
            if entity.get('last_updated'):
                click.echo(f"  - Last Updated: {entity['last_updated']}")
            click.echo()
        
        if logbook_entries:
            click.echo(f"## Recent Error Log Entries ({len(logbook_entries)})\n")
            for entry in logbook_entries[:20]:
                click.echo(f"**{entry.get('name', 'Unknown')}**")
                if entry.get('when'):
                    click.echo(f"  - When: {entry['when']}")
                if entry.get('entity_id'):
                    click.echo(f"  - Entity: {entry['entity_id']}")
                click.echo()
    else:  # table format
        click.echo("=== Home Assistant Error Log ===\n")
        
        click.echo(f"## Unavailable Entities ({len(unavailable)})\n")
        if unavailable:
            click.echo(f"{'Entity ID':<50} {'Friendly Name':<40} {'Last Updated':<30}")
            click.echo("-" * 120)
            for entity in unavailable:
                name = entity['friendly_name']
                if len(name) > 38:
                    name = name[:35] + '...'
                last_upd = entity.get('last_updated', '-') or '-'
                if len(last_upd) > 28:
                    last_upd = last_upd[:25] + '...'
                click.echo(f"{entity['entity_id']:<50} {name:<40} {last_upd:<30}")
        else:
            click.echo("No unavailable entities found.")
        click.echo()
        
        if logbook_entries:
            click.echo(f"## Recent Error Log Entries ({len(logbook_entries)})\n")
            click.echo(f"{'Name':<40} {'When':<30} {'Entity':<40}")
            click.echo("-" * 110)
            for entry in logbook_entries[:20]:
                name = entry.get('name', 'Unknown')
                if len(name) > 38:
                    name = name[:35] + '...'
                when = entry.get('when', '-') or '-'
                if len(when) > 28:
                    when = when[:25] + '...'
                entity_id = entry.get('entity_id', '-') or '-'
                if len(entity_id) > 38:
                    entity_id = entity_id[:35] + '...'
                click.echo(f"{name:<40} {when:<30} {entity_id:<40}")
            click.echo()


