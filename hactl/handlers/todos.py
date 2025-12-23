"""
Handler migrated from get/todos.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_todos(format_type='table'):
    """
    Handler for todos

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
    
    # Filter todos
    todos = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('todo.'):
            attrs = state.get('attributes', {})
            todo_data = {
                'entity_id': entity_id,
                'state': state.get('state', '0'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'item_count': int(state.get('state', 0)) if state.get('state', '0').isdigit() else 0
            }
            todos.append(todo_data)
    
    todos.sort(key=lambda x: x['friendly_name'].lower())
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(todos, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Todo Lists")
        click.echo("---")
        click.echo(json_to_yaml(todos))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Todo Lists ===\n")
        click.echo(f"Total Todo Lists: {len(todos)}\n")
        
        for todo in todos:
            click.echo(f"**{todo['friendly_name']}** (`{todo['entity_id']}`)")
            click.echo(f"  - Item Count: {todo['item_count']}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Todo Lists ===\n")
        click.echo(f"Total Todo Lists: {len(todos)}\n")
        click.echo(f"{'Todo List':<50} {'Item Count':<15}")
        click.echo("-" * 65)
        
        for todo in todos:
            name = todo['friendly_name']
            if len(name) > 48:
                name = name[:45] + '...'
            click.echo(f"{name:<50} {todo['item_count']:<15}")
        click.echo()


