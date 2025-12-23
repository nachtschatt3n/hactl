"""
Handler migrated from get/history.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_history(format_type='table'):
    """
    Handler for history

    Args:
        format_type: Output format
    """

    # Get entity_id and format from command line
    entity_id = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1] in ['table', 'json', 'detail', 'yaml'] else None
    format_type = sys.argv[-1] if len(sys.argv) > 1 and sys.argv[-1] in ['table', 'json', 'detail', 'yaml'] else 'table'
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Calculate time range (last 24 hours)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    
    if entity_id:
        # Get history for specific entity
        url = f"{HASS_URL}/api/history/period/{start_time.isoformat()}"
        params = f"?filter_entity_id={entity_id}"
        history_data = make_api_request(url + params, HASS_TOKEN)
        
        if not history_data or not history_data:
            click.echo(f"No history found for entity: {entity_id}", file=sys.stderr)
            return
        
        # Format entity history
        history_list = []
        for entry_list in history_data:
            for entry in entry_list:
                history_list.append({
                    'entity_id': entry.get('entity_id'),
                    'state': entry.get('state'),
                    'last_changed': entry.get('last_changed'),
                    'last_updated': entry.get('last_updated'),
                    'attributes': entry.get('attributes', {})
                })
        
        result = {
            'entity_id': entity_id,
            'period': f"{start_time.isoformat()} to {end_time.isoformat()}",
            'state_changes': len(history_list),
            'history': history_list
        }
    else:
        # Get logbook for recent activity
        logbook_url = f"{HASS_URL}/api/logbook/{start_time.isoformat()}"
        logbook_data = make_api_request(logbook_url, HASS_TOKEN)
        
        # Process logbook entries
        activity_summary = {}
        recent_activity = []
        
        for entry in logbook_data[:100]:  # Limit to 100 most recent
            entity = entry.get('entity_id', 'unknown')
            if entity not in activity_summary:
                activity_summary[entity] = 0
            activity_summary[entity] += 1
            
            recent_activity.append({
                'when': entry.get('when'),
                'name': entry.get('name'),
                'entity_id': entry.get('entity_id'),
                'state': entry.get('state'),
                'domain': entry.get('domain')
            })
        
        # Sort by activity count
        most_active = sorted(activity_summary.items(), key=lambda x: -x[1])[:20]
        
        result = {
            'period': f"{start_time.isoformat()} to {end_time.isoformat()}",
            'total_events': len(logbook_data),
            'most_active_entities': [{'entity_id': eid, 'event_count': count} for eid, count in most_active],
            'recent_activity': recent_activity[:50]
        }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant History")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        if entity_id:
            click.echo(f"=== History for {entity_id} ===\n")
            click.echo(f"Period: {result['period']}")
            click.echo(f"State Changes: {result['state_changes']}\n")
            for entry in result['history'][:20]:
                click.echo(f"**{entry['last_changed']}**")
                click.echo(f"  - State: {entry['state']}")
                click.echo()
        else:
            click.echo("=== Recent Activity Summary ===\n")
            click.echo(f"Period: {result['period']}")
            click.echo(f"Total Events: {result['total_events']}\n")
            click.echo("## Most Active Entities\n")
            for item in result['most_active_entities']:
                click.echo(f"  {item['entity_id']}: {item['event_count']} events")
            click.echo("\n## Recent Activity\n")
            for entry in result['recent_activity'][:20]:
                click.echo(f"  {entry['when']} - {entry['name']} ({entry.get('entity_id', 'N/A')})")
    else:  # table format
        if entity_id:
            click.echo(f"=== History for {entity_id} ===\n")
            click.echo(f"Period: {result['period']}")
            click.echo(f"State Changes: {result['state_changes']}\n")
            click.echo(f"{'Time':<30} {'State':<30}")
            click.echo("-" * 60)
            for entry in result['history'][:50]:
                time_str = entry['last_changed'][:19] if entry.get('last_changed') else 'N/A'
                click.echo(f"{time_str:<30} {entry['state']:<30}")
        else:
            click.echo("=== Recent Activity Summary ===\n")
            click.echo(f"Period: {result['period']}")
            click.echo(f"Total Events: {result['total_events']}\n")
            click.echo("## Most Active Entities\n")
            click.echo(f"{'Entity ID':<50} {'Event Count':<15}")
            click.echo("-" * 65)
            for item in result['most_active_entities']:
                click.echo(f"{item['entity_id']:<50} {item['event_count']:<15}")
            click.echo("\n## Recent Activity (Last 20)\n")
            click.echo(f"{'When':<30} {'Name':<40} {'Entity':<40}")
            click.echo("-" * 110)
            for entry in result['recent_activity'][:20]:
                when = entry['when'][:19] if entry.get('when') else 'N/A'
                name = entry['name'][:38] if len(entry.get('name', '')) > 38 else entry.get('name', 'N/A')
                entity = entry.get('entity_id', 'N/A')[:38] if len(entry.get('entity_id', 'N/A')) > 38 else entry.get('entity_id', 'N/A')
                click.echo(f"{when:<30} {name:<40} {entity:<40}")


