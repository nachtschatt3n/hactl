"""
Memory management utilities for AI context
"""

import os
import json
import click
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from hactl.core import load_config, make_api_request


# Base memory directory
MEMORY_DIR = Path(__file__).parent.parent.parent / 'memory'


def ensure_memory_dir(category: Optional[str] = None) -> Path:
    """Ensure memory directory exists"""
    if category:
        path = MEMORY_DIR / category
    else:
        path = MEMORY_DIR

    path.mkdir(parents=True, exist_ok=True)
    return path


def add_note(category: str, item_id: str, note: str):
    """
    Add a contextual note to memory.

    Args:
        category: Category (sensor, device, automation, dashboard)
        item_id: Entity ID or identifier
        note: Contextual note
    """
    category_dir = ensure_memory_dir(f"{category}s")
    notes_file = category_dir / "notes.json"

    # Load existing notes
    if notes_file.exists():
        with open(notes_file, 'r') as f:
            notes = json.load(f)
    else:
        notes = {}

    # Add or update note
    if item_id not in notes:
        notes[item_id] = []

    notes[item_id].append({
        'note': note,
        'timestamp': datetime.now().isoformat()
    })

    # Save notes
    with open(notes_file, 'w') as f:
        json.dump(notes, f, indent=2)

    click.secho(f"✓ Added note for {item_id} in {category}s", fg='green')
    click.echo(f"  Note: {note}")


def show_notes(category: str, item_id: Optional[str] = None):
    """
    Show memory notes for a category or specific item.

    Args:
        category: Category (sensor, device, automation, dashboard)
        item_id: Optional specific entity ID
    """
    category_dir = MEMORY_DIR / f"{category}s"
    notes_file = category_dir / "notes.json"

    if not notes_file.exists():
        click.secho(f"No notes found for {category}s", fg='yellow')
        return

    with open(notes_file, 'r') as f:
        notes = json.load(f)

    if item_id:
        # Show notes for specific item
        if item_id in notes:
            click.secho(f"Notes for {item_id}:", fg='green')
            for note_entry in notes[item_id]:
                timestamp = note_entry['timestamp']
                note = note_entry['note']
                click.echo(f"  [{timestamp}] {note}")
        else:
            click.secho(f"No notes found for {item_id}", fg='yellow')
    else:
        # Show all notes in category
        click.secho(f"All notes in {category}s:", fg='green')
        for entity_id, note_list in notes.items():
            click.echo(f"\n{entity_id}:")
            for note_entry in note_list:
                timestamp = note_entry['timestamp']
                note = note_entry['note']
                click.echo(f"  [{timestamp}] {note}")


def edit_file(file_path: str):
    """
    Open a memory file in the user's editor.

    Args:
        file_path: Relative path from memory/ directory
    """
    full_path = MEMORY_DIR / file_path

    # Ensure parent directory exists
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Create file if it doesn't exist
    if not full_path.exists():
        full_path.write_text("# Memory File\n\n")
        click.secho(f"Created new file: {full_path}", fg='green')

    # Get editor from environment
    editor = os.environ.get('EDITOR', 'nano')

    click.echo(f"Opening {full_path} with {editor}...")
    os.system(f"{editor} {full_path}")


def sync_from_hass(categories: Optional[List[str]] = None):
    """
    Sync current Home Assistant state to memory.

    Args:
        categories: Optional list of categories to sync (devices, sensors, automations, dashboards)
    """
    HASS_URL, HASS_TOKEN = load_config()

    if categories is None:
        categories = ['devices', 'sensors', 'automations', 'dashboards']

    click.echo("Syncing Home Assistant state to memory...")
    click.echo()

    synced = {}

    for category in categories:
        try:
            if category == 'devices':
                synced['devices'] = sync_devices(HASS_URL, HASS_TOKEN)
            elif category == 'sensors':
                synced['sensors'] = sync_sensors(HASS_URL, HASS_TOKEN)
            elif category == 'automations':
                synced['automations'] = sync_automations(HASS_URL, HASS_TOKEN)
            elif category == 'dashboards':
                synced['dashboards'] = sync_dashboards(HASS_URL, HASS_TOKEN)
        except Exception as e:
            click.secho(f"✗ Failed to sync {category}: {str(e)}", fg='red')

    click.echo()
    click.secho("Memory sync complete! AI context updated.", fg='green')

    # Show summary
    for category, count in synced.items():
        click.echo(f"  {category}: {count} items")


def sync_devices(hass_url: str, hass_token: str) -> int:
    """Sync devices to memory"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract unique devices
    devices = {}
    for state in states:
        entity_id = state.get('entity_id', '')
        attrs = state.get('attributes', {})

        if 'device_id' in attrs:
            device_id = attrs['device_id']
            if device_id not in devices:
                devices[device_id] = {
                    'device_id': device_id,
                    'entities': [],
                    'friendly_name': attrs.get('friendly_name', ''),
                    'model': attrs.get('model', ''),
                    'manufacturer': attrs.get('manufacturer', '')
                }
            devices[device_id]['entities'].append(entity_id)

    # Save to memory
    devices_dir = ensure_memory_dir('devices')
    devices_file = devices_dir / 'devices.json'

    with open(devices_file, 'w') as f:
        json.dump(list(devices.values()), f, indent=2)

    click.secho(f"✓ Devices: {len(devices)} devices saved", fg='green')
    return len(devices)


def sync_sensors(hass_url: str, hass_token: str) -> int:
    """Sync sensors to memory"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract sensors
    sensors = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('sensor.'):
            sensors.append({
                'entity_id': entity_id,
                'friendly_name': state.get('attributes', {}).get('friendly_name', ''),
                'device_class': state.get('attributes', {}).get('device_class', ''),
                'unit_of_measurement': state.get('attributes', {}).get('unit_of_measurement', ''),
                'state': state.get('state', 'unknown')
            })

    # Save to memory
    sensors_dir = ensure_memory_dir('sensors')
    sensors_file = sensors_dir / 'sensors.json'

    with open(sensors_file, 'w') as f:
        json.dump(sensors, f, indent=2)

    click.secho(f"✓ Sensors: {len(sensors)} sensors saved", fg='green')
    return len(sensors)


def sync_automations(hass_url: str, hass_token: str) -> int:
    """Sync automations to memory"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract automations
    automations = []
    for state in states:
        entity_id = state.get('entity_id', '')
        if entity_id.startswith('automation.'):
            automations.append({
                'entity_id': entity_id,
                'friendly_name': state.get('attributes', {}).get('friendly_name', ''),
                'state': state.get('state', 'unknown'),
                'last_triggered': state.get('attributes', {}).get('last_triggered', '')
            })

    # Save to memory
    automations_dir = ensure_memory_dir('automations')
    automations_file = automations_dir / 'automations.json'

    with open(automations_file, 'w') as f:
        json.dump(automations, f, indent=2)

    click.secho(f"✓ Automations: {len(automations)} automations saved", fg='green')
    return len(automations)


def sync_dashboards(hass_url: str, hass_token: str) -> int:
    """Sync dashboards to memory"""
    # For now, just create a placeholder
    # Full dashboard sync would require WebSocket access
    dashboards_dir = ensure_memory_dir('dashboards')
    dashboards_file = dashboards_dir / 'dashboards.json'

    dashboards = {
        'note': 'Dashboard sync requires WebSocket connection',
        'timestamp': datetime.now().isoformat()
    }

    with open(dashboards_file, 'w') as f:
        json.dump(dashboards, f, indent=2)

    click.secho(f"✓ Dashboards: metadata saved", fg='green')
    return 1


def list_memory():
    """List all memory contents"""
    click.secho("Memory Contents:", fg='green')
    click.echo()

    categories = ['sensors', 'devices', 'automations', 'dashboards', 'context']

    for category in categories:
        category_dir = MEMORY_DIR / category
        if category_dir.exists():
            files = list(category_dir.glob('*'))
            click.echo(f"{category}/")
            for file in files:
                size = file.stat().st_size
                click.echo(f"  {file.name} ({size} bytes)")
        else:
            click.secho(f"{category}/ (empty)", fg='yellow')
        click.echo()
