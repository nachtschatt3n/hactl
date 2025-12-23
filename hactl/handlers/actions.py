"""
Handler migrated from get/actions.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_actions(format_type='table'):
    """
    Handler for actions

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
    
    # Filter for service calls (actions)
    service_calls = []
    automation_executions = []
    script_executions = []
    
    for entry in logbook_data:
        domain = entry.get('domain', '')
        entity_id = entry.get('entity_id', '')
        
        # Filter service calls
        if entry.get('context', {}).get('event_type') == 'call_service' or 'service' in entry.get('name', '').lower():
            service_calls.append({
                'when': entry.get('when'),
                'name': entry.get('name'),
                'entity_id': entry.get('entity_id'),
                'domain': domain,
                'state': entry.get('state')
            })
        
        # Filter automation executions
        if entity_id and entity_id.startswith('automation.'):
            automation_executions.append({
                'when': entry.get('when'),
                'name': entry.get('name'),
                'entity_id': entity_id,
                'state': entry.get('state')
            })
        
        # Filter script executions
        if entity_id and entity_id.startswith('script.'):
            script_executions.append({
                'when': entry.get('when'),
                'name': entry.get('name'),
                'entity_id': entity_id,
                'state': entry.get('state')
            })
    
    result = {
        'period': f"{start_time.isoformat()} to {end_time.isoformat()}",
        'service_calls': service_calls[:100],
        'automation_executions': automation_executions[:100],
        'script_executions': script_executions[:100],
        'summary': {
            'total_service_calls': len(service_calls),
            'total_automation_executions': len(automation_executions),
            'total_script_executions': len(script_executions)
        }
    }
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Actions")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Actions ===\n")
        click.echo(f"Period: {result['period']}\n")
        
        click.echo(f"## Summary\n")
        click.echo(f"  Service Calls: {result['summary']['total_service_calls']}")
        click.echo(f"  Automation Executions: {result['summary']['total_automation_executions']}")
        click.echo(f"  Script Executions: {result['summary']['total_script_executions']}")
        click.echo()
        
        if result['service_calls']:
            click.echo(f"## Service Calls (Last 20)\n")
            for call in result['service_calls'][:20]:
                click.echo(f"  {call['when']} - {call['name']} ({call.get('entity_id', 'N/A')})")
            click.echo()
        
        if result['automation_executions']:
            click.echo(f"## Automation Executions (Last 20)\n")
            for exec_item in result['automation_executions'][:20]:
                click.echo(f"  {exec_item['when']} - {exec_item['name']} ({exec_item['entity_id']})")
            click.echo()
        
        if result['script_executions']:
            click.echo(f"## Script Executions (Last 20)\n")
            for exec_item in result['script_executions'][:20]:
                click.echo(f"  {exec_item['when']} - {exec_item['name']} ({exec_item['entity_id']})")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Actions ===\n")
        click.echo(f"Period: {result['period']}\n")
        
        click.echo("## Summary\n")
        click.echo(f"{'Type':<30} {'Count':<15}")
        click.echo("-" * 45)
        click.echo(f"{'Service Calls':<30} {result['summary']['total_service_calls']:<15}")
        click.echo(f"{'Automation Executions':<30} {result['summary']['total_automation_executions']:<15}")
        click.echo(f"{'Script Executions':<30} {result['summary']['total_script_executions']:<15}")
        click.echo()
        
        if result['service_calls']:
            click.echo("## Service Calls (Last 20)\n")
            click.echo(f"{'When':<30} {'Name':<40} {'Entity':<40}")
            click.echo("-" * 110)
            for call in result['service_calls'][:20]:
                when = call['when'][:19] if call.get('when') else 'N/A'
                name = call['name'][:38] if len(call.get('name', '')) > 38 else call.get('name', 'N/A')
                entity = call.get('entity_id', 'N/A')[:38] if len(call.get('entity_id', 'N/A')) > 38 else call.get('entity_id', 'N/A')
                click.echo(f"{when:<30} {name:<40} {entity:<40}")
            click.echo()
        
        if result['automation_executions']:
            click.echo("## Automation Executions (Last 20)\n")
            click.echo(f"{'When':<30} {'Name':<40} {'Entity':<40}")
            click.echo("-" * 110)
            for exec_item in result['automation_executions'][:20]:
                when = exec_item['when'][:19] if exec_item.get('when') else 'N/A'
                name = exec_item['name'][:38] if len(exec_item.get('name', '')) > 38 else exec_item.get('name', 'N/A')
                entity = exec_item['entity_id'][:38] if len(exec_item.get('entity_id', '')) > 38 else exec_item.get('entity_id', 'N/A')
                click.echo(f"{when:<30} {name:<40} {entity:<40}")
            click.echo()
        
        if result['script_executions']:
            click.echo("## Script Executions (Last 20)\n")
            click.echo(f"{'When':<30} {'Name':<40} {'Entity':<40}")
            click.echo("-" * 110)
            for exec_item in result['script_executions'][:20]:
                when = exec_item['when'][:19] if exec_item.get('when') else 'N/A'
                name = exec_item['name'][:38] if len(exec_item.get('name', '')) > 38 else exec_item.get('name', 'N/A')
                entity = exec_item['entity_id'][:38] if len(exec_item.get('entity_id', '')) > 38 else exec_item.get('entity_id', 'N/A')
                click.echo(f"{when:<30} {name:<40} {entity:<40}")
            click.echo()


