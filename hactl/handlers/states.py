"""
Entity states operations handler
"""

import json
import click
from collections import Counter, defaultdict
from hactl.core import load_config, make_api_request, json_to_yaml


def get_states(format_type='table', entity_filter=None, domain_filter=None):
    """
    Get comprehensive entity state overview.

    Args:
        format_type: Output format (table, json, yaml, detail)
        entity_filter: Filter by entity ID pattern (optional)
        domain_filter: Filter by domain (optional)
    """
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()

    # Fetch all states
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)

    # Apply filters if provided
    if entity_filter or domain_filter:
        filtered_states = []
        for state in states:
            entity_id = state.get('entity_id', '')
            domain = entity_id.split('.')[0] if '.' in entity_id else 'unknown'

            if domain_filter and domain != domain_filter:
                continue
            if entity_filter and entity_filter not in entity_id:
                continue

            filtered_states.append(state)
        states = filtered_states

    # Analyze states
    domain_counts = Counter()
    state_distribution = Counter()
    unavailable_entities = []
    entity_attributes_summary = defaultdict(set)

    for state in states:
        entity_id = state.get('entity_id', '')
        domain = entity_id.split('.')[0] if '.' in entity_id else 'unknown'
        domain_counts[domain] += 1

        entity_state = state.get('state', 'unknown')
        state_distribution[entity_state] += 1

        if entity_state == 'unavailable':
            unavailable_entities.append({
                'entity_id': entity_id,
                'friendly_name': state.get('attributes', {}).get('friendly_name', entity_id),
                'last_updated': state.get('last_updated')
            })

        # Collect attribute types
        attrs = state.get('attributes', {})
        for attr_key in attrs.keys():
            entity_attributes_summary[attr_key].add(domain)

    # Format results
    result = {
        'total_entities': len(states),
        'domains': dict(sorted(domain_counts.items())),
        'state_distribution': dict(state_distribution),
        'unavailable_count': len(unavailable_entities),
        'unavailable_entities': unavailable_entities[:50],  # Limit to 50
        'common_attributes': {k: len(v) for k, v in sorted(entity_attributes_summary.items(), key=lambda x: -len(x[1]))[:20]}
    }

    # Format output
    if format_type == 'json':
        click.echo(json.dumps(result, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Entity States Overview")
        click.echo("---")
        click.echo(json_to_yaml(result))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Entity States Overview ===\n")
        click.echo(f"Total Entities: {result['total_entities']}\n")

        click.echo("## Entity Counts by Domain\n")
        for domain, count in sorted(result['domains'].items(), key=lambda x: -x[1]):
            click.echo(f"  {domain}: {count}")
        click.echo()

        click.echo("## State Distribution\n")
        for state, count in sorted(result['state_distribution'].items(), key=lambda x: -x[1])[:20]:
            click.echo(f"  {state}: {count}")
        click.echo()

        if result['unavailable_count'] > 0:
            click.echo(f"## Unavailable Entities ({result['unavailable_count']})\n")
            for entity in result['unavailable_entities'][:20]:
                click.echo(f"  - {entity['entity_id']} ({entity['friendly_name']})")
            if result['unavailable_count'] > 20:
                click.echo(f"  ... and {result['unavailable_count'] - 20} more")
            click.echo()

        click.echo("## Common Attributes\n")
        for attr, domain_count in list(result['common_attributes'].items())[:10]:
            click.echo(f"  {attr}: used by {domain_count} domains")
    else:  # table format
        click.echo("=== Home Assistant Entity States Overview ===\n")
        click.echo(f"Total Entities: {result['total_entities']}\n")

        click.echo("## Entity Counts by Domain\n")
        click.echo(f"{'Domain':<30} {'Count':<10}")
        click.echo("-" * 40)
        for domain, count in sorted(result['domains'].items(), key=lambda x: -x[1]):
            click.echo(f"{domain:<30} {count:<10}")
        click.echo()

        click.echo("## State Distribution (Top 20)\n")
        click.echo(f"{'State':<30} {'Count':<10}")
        click.echo("-" * 40)
        for state, count in sorted(result['state_distribution'].items(), key=lambda x: -x[1])[:20]:
            state_display = state if len(state) <= 28 else state[:25] + '...'
            click.echo(f"{state_display:<30} {count:<10}")
        click.echo()

        if result['unavailable_count'] > 0:
            click.echo(f"## Unavailable Entities ({result['unavailable_count']})\n")
            click.echo(f"{'Entity ID':<50} {'Friendly Name':<40}")
            click.echo("-" * 90)
            for entity in result['unavailable_entities'][:20]:
                name = entity['friendly_name']
                if len(name) > 38:
                    name = name[:35] + '...'
                click.echo(f"{entity['entity_id']:<50} {name:<40}")
            if result['unavailable_count'] > 20:
                click.echo(f"... and {result['unavailable_count'] - 20} more")
            click.echo()
