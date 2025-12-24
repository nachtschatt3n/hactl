"""
Handler migrated from get/activity.py
"""

import json
import click
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hactl.core import load_config, make_api_request, json_to_yaml

def get_activity(format_type='table'):
    """
    Handler for activity

    Args:
        format_type: Output format
    """

    # Get format from command line
    # format_type passed as parameter
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Calculate time range (last 24 hours)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    
    # Get logbook entries
    logbook_url = f"{HASS_URL}/api/logbook/{start_time.isoformat()}"
    logbook_data = make_api_request(logbook_url, HASS_TOKEN)
    
    # Analyze activity
    entity_activity = Counter()
    domain_activity = Counter()
    activity_by_hour = defaultdict(int)
    recent_changes = []
    
    for entry in logbook_data:
        entity_id = entry.get('entity_id', 'unknown')
        domain = entity_id.split('.')[0] if '.' in entity_id else 'unknown'
        
        entity_activity[entity_id] += 1
        domain_activity[domain] += 1
        
        # Extract hour from timestamp
        when = entry.get('when')
        if when:
            try:
                hour = datetime.fromisoformat(when.replace('Z', '+00:00')).hour
                activity_by_hour[hour] += 1
            except:
                pass
        
        recent_changes.append({
            'when': entry.get('when'),
            'name': entry.get('name'),
            'entity_id': entry.get('entity_id'),
            'state': entry.get('state'),
            'domain': domain
        })
    
    # Get most active entities
    most_active_entities = [{'entity_id': eid, 'count': count} 
                           for eid, count in entity_activity.most_common(20)]
    
    # Format activity by hour
    hourly_activity = [{'hour': hour, 'count': count} 
                      for hour, count in sorted(activity_by_hour.items())]
    
    result = {
        'period': f"{start_time.isoformat()} to {end_time.isoformat()}",
        'total_events': len(logbook_data),
        'most_active_entities': most_active_entities,
        'domain_activity': dict(domain_activity.most_common(10)),
        'hourly_activity': hourly_activity,
        'recent_changes': recent_changes[:50]
    }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Activity")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Activity ===\n")
        click.echo(f"Period: {result['period']}")
        click.echo(f"Total Events: {result['total_events']}\n")
        
        click.echo("## Most Active Entities\n")
        for item in result['most_active_entities']:
            click.echo(f"  {item['entity_id']}: {item['count']} events")
        click.echo()
        
        click.echo("## Activity by Domain\n")
        for domain, count in sorted(result['domain_activity'].items(), key=lambda x: -x[1]):
            click.echo(f"  {domain}: {count} events")
        click.echo()
        
        click.echo("## Activity by Hour\n")
        for hour_data in result['hourly_activity']:
            hour = hour_data['hour']
            count = hour_data['count']
            bar = '█' * (count // max(1, max(h['count'] for h in result['hourly_activity']) // 20))
            click.echo(f"  {hour:02d}:00 {bar} {count}")
        click.echo()
        
        click.echo("## Recent Changes (Last 20)\n")
        for entry in result['recent_changes'][:20]:
            click.echo(f"  {entry['when']} - {entry['name']} ({entry['entity_id']})")
    else:  # table format
        click.echo("=== Home Assistant Activity ===\n")
        click.echo(f"Period: {result['period']}")
        click.echo(f"Total Events: {result['total_events']}\n")
        
        click.echo("## Most Active Entities\n")
        click.echo(f"{'Entity ID':<50} {'Event Count':<15}")
        click.echo("-" * 65)
        for item in result['most_active_entities']:
            click.echo(f"{item['entity_id']:<50} {item['count']:<15}")
        click.echo()
        
        click.echo("## Activity by Domain\n")
        click.echo(f"{'Domain':<30} {'Event Count':<15}")
        click.echo("-" * 45)
        for domain, count in sorted(result['domain_activity'].items(), key=lambda x: -x[1]):
            click.echo(f"{domain:<30} {count:<15}")
        click.echo()
        
        click.echo("## Recent Changes (Last 20)\n")
        click.echo(f"{'When':<30} {'Name':<40} {'Entity':<40}")
        click.echo("-" * 110)
        for entry in result['recent_changes'][:20]:
            when = entry['when'][:19] if entry.get('when') else 'N/A'
            name = entry['name'][:38] if len(entry.get('name', '')) > 38 else entry.get('name', 'N/A')
            entity = entry['entity_id'][:38] if len(entry.get('entity_id', '')) > 38 else entry.get('entity_id', 'N/A')
            click.echo(f"{when:<30} {name:<40} {entity:<40}")


