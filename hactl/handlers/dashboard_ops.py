"""
Dashboard update operations handler
"""

import json
import click
from hactl.core import load_config
from hactl.core.websocket import WebSocketClient

# Try to import yaml, but make it optional
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None


def load_yaml_file(yaml_file):
    """Load YAML file and convert to dict"""
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            if HAS_YAML:
                try:
                    return yaml.safe_load(f)
                except Exception:
                    pass
            # Fallback to JSON
            f.seek(0)
            return json.load(f)
    except FileNotFoundError:
        raise click.ClickException(f"File not found: {yaml_file}")
    except Exception as e:
        raise click.ClickException(f"Error loading file: {e}")


def update_dashboard(url_path, yaml_file):
    """Update an existing dashboard"""
    HASS_URL, HASS_TOKEN = load_config()
    config = load_yaml_file(yaml_file)

    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()
        # WebSocket call raises exception on failure, so if we get here it succeeded
        ws.call("lovelace/config/save", url_path=url_path, config=config)
        click.secho(f"✓ Successfully updated dashboard: {url_path}", fg='green')
    finally:
        ws.close()


def create_dashboard(url_path, yaml_file):
    """Create a new dashboard"""
    HASS_URL, HASS_TOKEN = load_config()
    config = load_yaml_file(yaml_file)

    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()
        # WebSocket call raises exception on failure, so if we get here it succeeded
        ws.call("lovelace/config/save", url_path=url_path, config=config)
        click.secho(f"✓ Successfully created dashboard: {url_path}", fg='green')
    finally:
        ws.close()
