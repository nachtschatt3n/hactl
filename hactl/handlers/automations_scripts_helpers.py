"""
Handler migrated from get/automations_scripts_helpers.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml


def get_automations(format_type='table'):
    """Get automations only"""
    return _get_filtered('automations', format_type)


def get_scripts(format_type='table'):
    """Get scripts only"""
    return _get_filtered('scripts', format_type)


def get_helpers(format_type='table'):
    """Get helpers only"""
    return _get_filtered('helpers', format_type)


def _get_filtered(type_filter='all', format_type='table'):
    """Internal function to get filtered entities"""
    HASS_URL, HASS_TOKEN = load_config()
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)

    # Filter by type
    automations = []
    scripts = []
    helpers = []

    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('automation.'):
            automations.append(state)
        elif entity_id.startswith('script.'):
            scripts.append(state)
        elif (entity_id.startswith('input_') or
              entity_id.startswith('counter.') or
              entity_id.startswith('timer.') or
              entity_id.startswith('todo.')):
            helpers.append(state)

    # Select which to show based on filter
    if type_filter == 'automations':
        items = automations
        title = "Automations"
    elif type_filter == 'scripts':
        items = scripts
        title = "Scripts"
    elif type_filter == 'helpers':
        items = helpers
        title = "Helpers"
    else:
        # Show all
        items = automations + scripts + helpers
        title = "Automations, Scripts, and Helpers"

    if format_type == 'json':
        click.echo(json.dumps([{
            'entity_id': item.get('entity_id'),
            'state': item.get('state'),
            'friendly_name': item.get('attributes', {}).get('friendly_name', '')
        } for item in items], indent=2))
    elif format_type == 'yaml':
        click.echo(f"# {title}")
        click.echo("---")
        for item in items:
            click.echo(f"- entity_id: {item.get('entity_id')}")
            click.echo(f"  state: {item.get('state')}")
            click.echo(f"  friendly_name: {item.get('attributes', {}).get('friendly_name', '')}")
    else:  # table
        click.echo(f"=== {title} ===\n")
        click.echo(f"Total: {len(items)}\n")
        for item in items:
            entity_id = item.get('entity_id')
            friendly_name = item.get('attributes', {}).get('friendly_name', entity_id)
            state = item.get('state', 'unknown')
            click.echo(f"{entity_id}: {friendly_name} ({state})")


def get_automations_scripts_helpers(format_type='table'):
    """
    Handler for automations_scripts_helpers

    Args:
        format_type: Output format
    """

    # Get format and type filter from command line
    # format_type passed as parameter
    type_filter = sys.argv[2] if len(sys.argv) > 2 else 'all'
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Fetch all states
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)
    
    # Filter by type
    automations = []
    scripts = []
    helpers = []
    
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('automation.'):
            automations.append(state)
        elif entity_id.startswith('script.'):
            scripts.append(state)
        elif (entity_id.startswith('input_') or 
              entity_id.startswith('counter.') or 
              entity_id.startswith('timer.') or 
              entity_id.startswith('todo.')):
            helpers.append(state)
    
    # Format results
    results = {
        'automations': [format_automation(a) for a in automations],
        'scripts': [format_script(s) for s in scripts],
        'helpers': [format_helper(h) for h in helpers]
    }
    
    # Apply type filter
    if type_filter == 'automations':
        results = {'automations': results['automations']}
    elif type_filter == 'scripts':
        results = {'scripts': results['scripts']}
    elif type_filter == 'helpers':
        results = {'helpers': results['helpers']}
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(results, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Automations, Scripts, and Helpers")
        click.echo("---")
        click.echo(json_to_yaml(results))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Automations, Scripts, and Helpers ===\n")
        
        if results.get('automations'):
            click.echo(f"## Automations ({len(results['automations'])})\n")
            for auto in results['automations']:
                click.echo(f"**{auto['friendly_name']}** (`{auto['entity_id']}`)")
                click.echo(f"  - State: {auto['state']}")
                click.echo(f"  - Mode: {auto['mode']}")
                if auto.get('current') and auto.get('max'):
                    click.echo(f"  - Current/Max: {auto['current']}/{auto['max']}")
                if auto.get('last_triggered'):
                    click.echo(f"  - Last Triggered: {auto['last_triggered']}")
                if auto.get('blueprint_id'):
                    click.echo(f"  - Blueprint: {auto['blueprint_id']}")
                click.echo()
        
        if results.get('scripts'):
            click.echo(f"## Scripts ({len(results['scripts'])})\n")
            for script in results['scripts']:
                click.echo(f"**{script['friendly_name']}** (`{script['entity_id']}`)")
                click.echo(f"  - State: {script['state']}")
                click.echo(f"  - Mode: {script['mode']}")
                if script.get('current') and script.get('max'):
                    click.echo(f"  - Current/Max: {script['current']}/{script['max']}")
                if script.get('last_triggered'):
                    click.echo(f"  - Last Triggered: {script['last_triggered']}")
                if script.get('last_action'):
                    click.echo(f"  - Last Action: {script['last_action']}")
                click.echo()
        
        if results.get('helpers'):
            click.echo(f"## Helpers ({len(results['helpers'])})\n")
            # Group by type
            by_type = defaultdict(list)
            for helper in results['helpers']:
                by_type[helper['type']].append(helper)
            
            for htype in sorted(by_type.keys()):
                click.echo(f"### {htype} ({len(by_type[htype])})\n")
                for helper in by_type[htype]:
                    click.echo(f"**{helper['friendly_name']}** (`{helper['entity_id']}`)")
                    click.echo(f"  - State: {helper['state']}")
                    if helper.get('unit_of_measurement'):
                        click.echo(f"  - Unit: {helper['unit_of_measurement']}")
                    if helper.get('min') is not None:
                        click.echo(f"  - Range: {helper['min']} - {helper.get('max', 'N/A')}")
                    if helper.get('options'):
                        opts = helper['options'][:5]
                        click.echo(f"  - Options: {', '.join(opts)}{'...' if len(helper['options']) > 5 else ''}")
                    click.echo()
    else:  # table format
        click.echo("=== Home Assistant Automations, Scripts, and Helpers ===\n")
        
        if results.get('automations'):
            click.echo(f"## Automations ({len(results['automations'])})\n")
            click.echo(f"{'Entity ID':<50} {'State':<10} {'Mode':<10} {'Last Triggered':<25} {'Blueprint':<30}")
            click.echo("-" * 125)
            for auto in sorted(results['automations'], key=lambda x: x['friendly_name']):
                last_trig = auto.get('last_triggered', 'Never') or 'Never'
                if last_trig != 'Never' and len(last_trig) > 20:
                    last_trig = last_trig[:17] + '...'
                blueprint = auto.get('blueprint_id', '') or ''
                if len(blueprint) > 28:
                    blueprint = blueprint[:25] + '...'
                click.echo(f"{auto['friendly_name']:<50} {auto['state']:<10} {auto['mode']:<10} {last_trig:<25} {blueprint:<30}")
            click.echo()
        
        if results.get('scripts'):
            click.echo(f"## Scripts ({len(results['scripts'])})\n")
            click.echo(f"{'Entity ID':<50} {'State':<10} {'Mode':<10} {'Last Triggered':<25}")
            click.echo("-" * 95)
            for script in sorted(results['scripts'], key=lambda x: x['friendly_name']):
                last_trig = script.get('last_triggered', 'Never') or 'Never'
                if last_trig != 'Never' and len(last_trig) > 20:
                    last_trig = last_trig[:17] + '...'
                click.echo(f"{script['friendly_name']:<50} {script['state']:<10} {script['mode']:<10} {last_trig:<25}")
            click.echo()
        
        if results.get('helpers'):
            click.echo(f"## Helpers ({len(results['helpers'])})\n")
            # Group by type
            by_type = defaultdict(list)
            for helper in results['helpers']:
                by_type[helper['type']].append(helper)
            
            for htype in sorted(by_type.keys()):
                click.echo(f"### {htype} ({len(by_type[htype])})\n")
                click.echo(f"{'Entity ID':<50} {'State':<15} {'Unit':<10} {'Range/Options':<30}")
                click.echo("-" * 105)
                for helper in sorted(by_type[htype], key=lambda x: x['friendly_name']):
                    unit = helper.get('unit_of_measurement', '') or ''
                    if helper.get('min') is not None:
                        range_str = f"{helper['min']}-{helper.get('max', 'N/A')}"
                    elif helper.get('options'):
                        opts = helper['options'][:3]
                        range_str = ', '.join(opts) + ('...' if len(helper['options']) > 3 else '')
                    else:
                        range_str = '-'
                    click.echo(f"{helper['friendly_name']:<50} {helper['state']:<15} {unit:<10} {range_str:<30}")
                click.echo()


