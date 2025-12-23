"""
Handler migrated from get/scenes.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_scenes(format_type='table'):
    """
    Handler for scenes

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
    
    # Filter scenes
    scenes = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('scene.'):
            attrs = state.get('attributes', {})
            scene_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'icon': attrs.get('icon'),
                'entity_id_list': attrs.get('entity_id', [])
            }
            scenes.append(scene_data)
    
    scenes.sort(key=lambda x: x['friendly_name'].lower())
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(scenes, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Scenes")
        click.echo("---")
        click.echo(json_to_yaml(scenes))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Scenes ===\n")
        click.echo(f"Total Scenes: {len(scenes)}\n")
        
        for scene in scenes:
            click.echo(f"**{scene['friendly_name']}** (`{scene['entity_id']}`)")
            click.echo(f"  - State: {scene['state']}")
            if scene.get('icon'):
                click.echo(f"  - Icon: {scene['icon']}")
            entity_count = len(scene.get('entity_id_list', []))
            click.echo(f"  - Entities: {entity_count}")
            if entity_count > 0:
                click.echo("  - Entity List:")
                for entity_id in scene['entity_id_list'][:10]:
                    click.echo(f"    - {entity_id}")
                if entity_count > 10:
                    click.echo(f"    ... and {entity_count - 10} more")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Scenes ===\n")
        click.echo(f"Total Scenes: {len(scenes)}\n")
        click.echo(f"{'Scene Name':<50} {'State':<15} {'Entities':<10}")
        click.echo("-" * 75)
        
        for scene in scenes:
            name = scene['friendly_name']
            if len(name) > 48:
                name = name[:45] + '...'
            entity_count = len(scene.get('entity_id_list', []))
            click.echo(f"{name:<50} {scene['state']:<15} {entity_count:<10}")
        click.echo()


