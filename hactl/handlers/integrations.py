"""
Handler migrated from get/integrations.py
"""

import json
import click
from collections import Counter
from hactl.core import load_config, make_api_request, json_to_yaml

def get_integrations(format_type='table'):
    """
    Handler for integrations

    Args:
        format_type: Output format
    """

    # Get format from command line
    # format_type passed as parameter
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Fetch integrations
    url = f"{HASS_URL}/api/config/config_entries/entry"
    integrations = make_api_request(url, HASS_TOKEN)
    
    # Format integrations
    integration_list = []
    for integration in integrations:
        integration_list.append({
            'title': integration.get('title', 'Unknown'),
            'domain': integration.get('domain', 'unknown'),
            'state': integration.get('state', 'unknown'),
            'entry_id': integration.get('entry_id'),
            'source': integration.get('source', 'unknown')
        })
    
    integration_list.sort(key=lambda x: (x['domain'], x['title']))
    
    # Count by state
    state_counts = Counter(integration.get('state', 'unknown') for integration in integration_list)
    
    # Format output
    if format_type == 'json':
        result = {
            'integrations': integration_list,
            'summary': {
                'total': len(integration_list),
                'by_state': dict(state_counts),
                'domains': sorted(set(i['domain'] for i in integration_list))
            }
        }
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        result = {
            'integrations': integration_list,
            'summary': {
                'total': len(integration_list),
                'by_state': dict(state_counts),
                'domains': sorted(set(i['domain'] for i in integration_list))
            }
        }
        click.echo("# Home Assistant Integrations")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Configured Integrations ===\n")
        for integration in integration_list:
            click.echo(f"**{integration['title']}** ({integration['domain']})")
            click.echo(f"  - State: {integration['state']}")
            click.echo(f"  - Source: {integration['source']}")
            click.echo()
        
        click.echo("\n=== Summary ===")
        click.echo(f"Total integrations: {len(integration_list)}")
        click.echo("\nBy state:")
        for state, count in sorted(state_counts.items()):
            click.echo(f"  {state}: {count}")
        click.echo("\nDomains:")
        for domain in sorted(set(i['domain'] for i in integration_list)):
            click.echo(f"  - {domain}")
    else:  # table format
        click.echo("=== Configured Integrations ===\n")
        for integration in integration_list:
            click.echo(f"{integration['title']} ({integration['domain']}) - State: {integration['state']}")
        
        click.echo("\n=== Summary ===")
        click.echo(f"Total integrations: {len(integration_list)}")
        click.echo("\nBy state:")
        for state, count in sorted(state_counts.items()):
            click.echo(f"  {state}: {count}")
        click.echo("\nDomains:")
        for domain in sorted(set(i['domain'] for i in integration_list)):
            click.echo(f"  - {domain}")


