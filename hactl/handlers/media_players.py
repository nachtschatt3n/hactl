"""
Handler migrated from get/media_players.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_media_players(format_type='table'):
    """
    Handler for media_players

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
    
    # Filter media players
    media_players = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('media_player.'):
            attrs = state.get('attributes', {})
            player_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'friendly_name': attrs.get('friendly_name', entity_id),
                'media_title': attrs.get('media_title'),
                'media_artist': attrs.get('media_artist'),
                'media_album_name': attrs.get('media_album_name'),
                'app_name': attrs.get('app_name'),
                'device_class': attrs.get('device_class'),
                'volume_level': attrs.get('volume_level'),
                'is_volume_muted': attrs.get('is_volume_muted', False),
                'supported_features': attrs.get('supported_features', 0)
            }
            media_players.append(player_data)
    
    media_players.sort(key=lambda x: x['friendly_name'].lower())
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(media_players, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Media Players")
        click.echo("---")
        click.echo(json_to_yaml(media_players))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Media Players ===\n")
        click.echo(f"Total Media Players: {len(media_players)}\n")
        
        for player in media_players:
            click.echo(f"**{player['friendly_name']}** (`{player['entity_id']}`)")
            click.echo(f"  - State: {player['state']}")
            if player.get('media_title'):
                click.echo(f"  - Now Playing: {player['media_title']}")
                if player.get('media_artist'):
                    click.echo(f"    Artist: {player['media_artist']}")
                if player.get('media_album_name'):
                    click.echo(f"    Album: {player['media_album_name']}")
            if player.get('app_name'):
                click.echo(f"  - App: {player['app_name']}")
            if player.get('volume_level') is not None:
                volume_pct = int(player['volume_level'] * 100)
                muted = " (muted)" if player.get('is_volume_muted') else ""
                click.echo(f"  - Volume: {volume_pct}%{muted}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Media Players ===\n")
        click.echo(f"Total Media Players: {len(media_players)}\n")
        click.echo(f"{'Player Name':<40} {'State':<20} {'Now Playing':<40}")
        click.echo("-" * 100)
        
        for player in media_players:
            name = player['friendly_name']
            if len(name) > 38:
                name = name[:35] + '...'
            now_playing = player.get('media_title') or player.get('app_name') or '-'
            if len(now_playing) > 38:
                now_playing = now_playing[:35] + '...'
            click.echo(f"{name:<40} {player['state']:<20} {now_playing:<40}")
        click.echo()


