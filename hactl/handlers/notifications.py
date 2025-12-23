"""
Handler migrated from get/notifications.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_notifications(format_type='table'):
    """
    Handler for notifications

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
    
    # Filter notifications
    notifications = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('persistent_notification.'):
            attrs = state.get('attributes', {})
            notification_data = {
                'entity_id': entity_id,
                'state': state.get('state', 'unknown'),
                'title': attrs.get('title', ''),
                'message': attrs.get('message', ''),
                'created_at': attrs.get('created_at'),
                'notification_id': attrs.get('notification_id', entity_id.split('.')[-1])
            }
            notifications.append(notification_data)
    
    notifications.sort(key=lambda x: x.get('created_at') or '', reverse=True)
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(notifications, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Persistent Notifications")
        click.echo("---")
        click.echo(json_to_yaml(notifications))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Persistent Notifications ===\n")
        click.echo(f"Total Notifications: {len(notifications)}\n")
        
        for notif in notifications:
            click.echo(f"**{notif.get('title', 'No Title')}** (ID: {notif['notification_id']})")
            click.echo(f"  - State: {notif['state']}")
            if notif.get('message'):
                msg = notif['message']
                if len(msg) > 100:
                    msg = msg[:97] + '...'
                click.echo(f"  - Message: {msg}")
            if notif.get('created_at'):
                click.echo(f"  - Created: {notif['created_at']}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Persistent Notifications ===\n")
        click.echo(f"Total Notifications: {len(notifications)}\n")
        if notifications:
            click.echo(f"{'Title':<40} {'State':<15} {'Created':<30}")
            click.echo("-" * 85)
            for notif in notifications:
                title = notif.get('title', 'No Title')
                if len(title) > 38:
                    title = title[:35] + '...'
                created = notif.get('created_at', '-') or '-'
                if len(created) > 28:
                    created = created[:25] + '...'
                click.echo(f"{title:<40} {notif['state']:<15} {created:<30}")
        else:
            click.echo("No persistent notifications found.")
        click.echo()


