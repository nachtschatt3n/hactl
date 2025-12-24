"""
Memory management utilities for AI context
Stores Home Assistant state as compact CSV files for efficient AI reading
"""

import os
import csv
import json
import click
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from hactl.core import load_config, make_api_request
from hactl.core.websocket import WebSocketClient


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
        categories = ['devices', 'sensors', 'automations', 'dashboards', 'hacs', 'areas',
                     'integrations', 'scripts', 'scenes', 'templates', 'entity_relationships',
                     'automation_stats', 'service_capabilities', 'battery_health',
                     'energy_data', 'automation_context', 'persons_presence']

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
            elif category == 'hacs':
                synced['hacs'] = sync_hacs(HASS_URL, HASS_TOKEN)
            elif category == 'areas':
                synced['areas'] = sync_areas(HASS_URL, HASS_TOKEN)
            elif category == 'integrations':
                synced['integrations'] = sync_integrations(HASS_URL, HASS_TOKEN)
            elif category == 'scripts':
                synced['scripts'] = sync_scripts(HASS_URL, HASS_TOKEN)
            elif category == 'scenes':
                synced['scenes'] = sync_scenes(HASS_URL, HASS_TOKEN)
            elif category == 'templates':
                synced['templates'] = sync_templates(HASS_URL, HASS_TOKEN)
            elif category == 'entity_relationships':
                synced['entity_relationships'] = sync_entity_relationships(HASS_URL, HASS_TOKEN)
            elif category == 'automation_stats':
                synced['automation_stats'] = sync_automation_stats(HASS_URL, HASS_TOKEN)
            elif category == 'service_capabilities':
                synced['service_capabilities'] = sync_service_capabilities(HASS_URL, HASS_TOKEN)
            elif category == 'battery_health':
                synced['battery_health'] = sync_battery_health(HASS_URL, HASS_TOKEN)
            elif category == 'energy_data':
                synced['energy_data'] = sync_energy_data(HASS_URL, HASS_TOKEN)
            elif category == 'automation_context':
                synced['automation_context'] = sync_automation_context(HASS_URL, HASS_TOKEN)
            elif category == 'persons_presence':
                synced['persons_presence'] = sync_persons_presence(HASS_URL, HASS_TOKEN)
        except Exception as e:
            click.secho(f"✗ Failed to sync {category}: {str(e)}", fg='red')

    click.echo()
    click.secho("Memory sync complete! AI context updated.", fg='green')

    # Show summary
    for category, count in synced.items():
        click.echo(f"  {category}: {count} items")


def sync_devices(hass_url: str, hass_token: str) -> int:
    """Sync devices to memory as CSV"""
    ws = WebSocketClient(hass_url, hass_token)
    try:
        ws.connect()
        device_list = ws.call('config/device_registry/list')
        ws.close()
    except Exception as e:
        click.secho(f"✗ Failed to get devices: {e}", fg='red')
        return 0

    # Save to CSV
    devices_dir = ensure_memory_dir()
    devices_file = devices_dir / 'devices.csv'

    with open(devices_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['device_id', 'name', 'manufacturer', 'model', 'area_id', 'sw_version'])

        for device in device_list:
            writer.writerow([
                device.get('id', ''),
                device.get('name') or device.get('name_by_user', ''),
                device.get('manufacturer', ''),
                device.get('model', ''),
                device.get('area_id', ''),
                device.get('sw_version', '')
            ])

    click.secho(f"✓ Devices: {len(device_list)} devices saved to devices.csv", fg='green')
    return len(device_list)


def sync_sensors(hass_url: str, hass_token: str) -> int:
    """Sync all entity states to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Save all states to CSV for comprehensive view
    memory_dir = ensure_memory_dir()
    states_file = memory_dir / 'states.csv'

    with open(states_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'domain', 'friendly_name', 'state', 'device_class', 'unit', 'area_id'])

        for state in states:
            entity_id = state.get('entity_id', '')
            domain = entity_id.split('.')[0] if '.' in entity_id else ''
            attrs = state.get('attributes', {})

            writer.writerow([
                entity_id,
                domain,
                attrs.get('friendly_name', ''),
                state.get('state', ''),
                attrs.get('device_class', ''),
                attrs.get('unit_of_measurement', ''),
                attrs.get('area_id', '')
            ])

    click.secho(f"✓ States: {len(states)} entities saved to states.csv", fg='green')
    return len(states)


def sync_automations(hass_url: str, hass_token: str) -> int:
    """Sync automations to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract automations
    automations = [s for s in states if s.get('entity_id', '').startswith('automation.')]

    # Save to CSV
    memory_dir = ensure_memory_dir()
    automations_file = memory_dir / 'automations.csv'

    with open(automations_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'friendly_name', 'state', 'last_triggered'])

        for auto in automations:
            attrs = auto.get('attributes', {})
            writer.writerow([
                auto.get('entity_id', ''),
                attrs.get('friendly_name', ''),
                auto.get('state', ''),
                attrs.get('last_triggered', '')
            ])

    click.secho(f"✓ Automations: {len(automations)} automations saved to automations.csv", fg='green')
    return len(automations)


def sync_dashboards(hass_url: str, hass_token: str) -> int:
    """Sync dashboards to memory as CSV"""
    ws = WebSocketClient(hass_url, hass_token)
    try:
        ws.connect()
        panels = ws.call("get_panels")
        ws.close()

        dashboards = []
        if isinstance(panels, dict):
            for key, panel in panels.items():
                if isinstance(panel, dict) and panel.get("component_name") == "lovelace":
                    url_path = panel.get("url_path") or key
                    if url_path != "lovelace":  # Skip default alias
                        dashboards.append({
                            'url_path': url_path,
                            'title': panel.get('title', key.title()),
                            'icon': panel.get('icon', '')
                        })

        # Save to CSV
        memory_dir = ensure_memory_dir()
        dashboards_file = memory_dir / 'dashboards.csv'

        with open(dashboards_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['url_path', 'title', 'icon'])

            for dash in dashboards:
                writer.writerow([
                    dash['url_path'],
                    dash['title'],
                    dash['icon']
                ])

        click.secho(f"✓ Dashboards: {len(dashboards)} dashboards saved to dashboards.csv", fg='green')
        return len(dashboards)
    except Exception as e:
        click.secho(f"✗ Failed to sync dashboards: {e}", fg='yellow')
        return 0


def sync_hacs(hass_url: str, hass_token: str) -> int:
    """Sync HACS installed repositories to memory as CSV"""
    ws = WebSocketClient(hass_url, hass_token)
    try:
        ws.connect()
        all_repos = ws.call("hacs/repositories/list")
        ws.close()

        # Filter for only installed repositories
        repositories = [r for r in all_repos if r.get('installed', False)] if isinstance(all_repos, list) else []

        # Save to CSV
        memory_dir = ensure_memory_dir()
        hacs_file = memory_dir / 'hacs.csv'

        with open(hacs_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['name', 'category', 'version', 'authors', 'description', 'full_name'])

            for repo in repositories:
                authors = ', '.join(repo.get('authors', [])) if repo.get('authors') else ''
                desc = repo.get('description', '')
                # Truncate long descriptions for CSV
                if len(desc) > 200:
                    desc = desc[:197] + '...'

                writer.writerow([
                    repo.get('name', ''),
                    repo.get('category', ''),
                    repo.get('installed_version', ''),
                    authors,
                    desc,
                    repo.get('full_name', '')
                ])

        click.secho(f"✓ HACS: {len(repositories)} repositories saved to hacs.csv", fg='green')
        return len(repositories)
    except Exception as e:
        click.secho(f"✗ Failed to sync HACS: {e}", fg='yellow')
        return 0


def sync_areas(hass_url: str, hass_token: str) -> int:
    """Sync areas to memory as CSV"""
    ws = WebSocketClient(hass_url, hass_token)
    try:
        ws.connect()
        area_list = ws.call('config/area_registry/list')
        ws.close()
    except Exception as e:
        click.secho(f"✗ Failed to get areas: {e}", fg='red')
        return 0

    # Save to CSV
    memory_dir = ensure_memory_dir()
    areas_file = memory_dir / 'areas.csv'

    with open(areas_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['area_id', 'name', 'aliases'])

        for area in area_list:
            aliases = ', '.join(area.get('aliases', [])) if area.get('aliases') else ''
            writer.writerow([
                area.get('area_id', ''),
                area.get('name', ''),
                aliases
            ])

    click.secho(f"✓ Areas: {len(area_list)} areas saved to areas.csv", fg='green')
    return len(area_list)


def sync_integrations(hass_url: str, hass_token: str) -> int:
    """Sync integrations to memory as CSV"""
    url = f"{hass_url}/api/config/config_entries/entry"
    integrations_data = make_api_request(url, hass_token)

    # Save to CSV
    memory_dir = ensure_memory_dir()
    integrations_file = memory_dir / 'integrations.csv'

    with open(integrations_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['domain', 'title', 'state', 'source'])

        for integration in integrations_data:
            writer.writerow([
                integration.get('domain', ''),
                integration.get('title', ''),
                integration.get('state', ''),
                integration.get('source', '')
            ])

    click.secho(f"✓ Integrations: {len(integrations_data)} integrations saved to integrations.csv", fg='green')
    return len(integrations_data)


def sync_scripts(hass_url: str, hass_token: str) -> int:
    """Sync scripts to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract scripts
    scripts = [s for s in states if s.get('entity_id', '').startswith('script.')]

    # Save to CSV
    memory_dir = ensure_memory_dir()
    scripts_file = memory_dir / 'scripts.csv'

    with open(scripts_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'friendly_name', 'last_triggered'])

        for script in scripts:
            attrs = script.get('attributes', {})
            writer.writerow([
                script.get('entity_id', ''),
                attrs.get('friendly_name', ''),
                attrs.get('last_triggered', '')
            ])

    click.secho(f"✓ Scripts: {len(scripts)} scripts saved to scripts.csv", fg='green')
    return len(scripts)


def sync_scenes(hass_url: str, hass_token: str) -> int:
    """Sync scenes to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract scenes
    scenes = [s for s in states if s.get('entity_id', '').startswith('scene.')]

    # Save to CSV
    memory_dir = ensure_memory_dir()
    scenes_file = memory_dir / 'scenes.csv'

    with open(scenes_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'friendly_name', 'icon'])

        for scene in scenes:
            attrs = scene.get('attributes', {})
            writer.writerow([
                scene.get('entity_id', ''),
                attrs.get('friendly_name', ''),
                attrs.get('icon', '')
            ])

    click.secho(f"✓ Scenes: {len(scenes)} scenes saved to scenes.csv", fg='green')
    return len(scenes)


def sync_templates(hass_url: str, hass_token: str) -> int:
    """Sync template entities and their formulas to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract template entities
    templates = []
    for state in states:
        entity_id = state.get('entity_id', '')
        attrs = state.get('attributes', {})

        # Check if it's a template sensor
        if attrs.get('state_class') or 'template' in entity_id:
            # Try to get template info from attributes
            templates.append({
                'entity_id': entity_id,
                'friendly_name': attrs.get('friendly_name', ''),
                'unit': attrs.get('unit_of_measurement', ''),
                'device_class': attrs.get('device_class', ''),
                'state_class': attrs.get('state_class', '')
            })

    # Save to CSV
    memory_dir = ensure_memory_dir()
    templates_file = memory_dir / 'templates.csv'

    with open(templates_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'friendly_name', 'unit', 'device_class', 'state_class'])

        for template in templates:
            writer.writerow([
                template['entity_id'],
                template['friendly_name'],
                template['unit'],
                template['device_class'],
                template['state_class']
            ])

    click.secho(f"✓ Templates: {len(templates)} template entities saved to templates.csv", fg='green')
    return len(templates)


def sync_entity_relationships(hass_url: str, hass_token: str) -> int:
    """Sync entity relationships extracted from area groupings to memory as CSV"""
    # Use WebSocket to get entity and device registries
    ws = WebSocketClient(hass_url, hass_token)
    try:
        ws.connect()
        entity_registry = ws.call('config/entity_registry/list')
        device_registry = ws.call('config/device_registry/list')
    finally:
        ws.close()

    relationships = []

    # Build device-to-area mapping
    device_areas = {}
    for device in device_registry:
        device_id = device.get('id')
        area_id = device.get('area_id')
        if device_id and area_id:
            device_areas[device_id] = area_id

    # Extract area-based relationships
    # Map entities to areas (either directly or via their device)
    area_groups = {}
    for entity in entity_registry:
        entity_id = entity.get('entity_id', '')

        # First try direct area assignment
        area_id = entity.get('area_id')

        # If no direct assignment, try via device
        if not area_id:
            device_id = entity.get('device_id')
            if device_id in device_areas:
                area_id = device_areas[device_id]

        if area_id:  # Only include entities that are assigned to an area
            if area_id not in area_groups:
                area_groups[area_id] = []
            area_groups[area_id].append(entity_id)

    # Create relationships for entities in same area
    # For each area, create relationships between adjacent entities
    for area_id, entities in area_groups.items():
        # Limit to avoid creating too many relationships for large areas
        entities_to_relate = entities[:20]  # Max 20 entities per area

        for i in range(len(entities_to_relate) - 1):
            relationships.append({
                'entity_id': entities_to_relate[i],
                'related_entity': entities_to_relate[i + 1],
                'relationship_type': 'same_area',
                'area_id': area_id
            })

    # Save to CSV
    memory_dir = ensure_memory_dir()
    relationships_file = memory_dir / 'entity_relationships.csv'

    with open(relationships_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'related_entity', 'relationship_type', 'context'])

        for rel in relationships:
            writer.writerow([
                rel['entity_id'],
                rel['related_entity'],
                rel['relationship_type'],
                rel.get('area_id', '')
            ])

    click.secho(f"✓ Entity Relationships: {len(relationships)} relationships saved to entity_relationships.csv", fg='green')
    return len(relationships)


def sync_automation_stats(hass_url: str, hass_token: str) -> int:
    """Sync automation statistics to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract automations with their stats
    automations = [s for s in states if s.get('entity_id', '').startswith('automation.')]

    stats = []
    for auto in automations:
        attrs = auto.get('attributes', {})
        stats.append({
            'entity_id': auto.get('entity_id', ''),
            'friendly_name': attrs.get('friendly_name', ''),
            'state': auto.get('state', ''),
            'last_triggered': attrs.get('last_triggered', ''),
            'mode': attrs.get('mode', 'single'),
            'current': attrs.get('current', 0)
        })

    # Save to CSV
    memory_dir = ensure_memory_dir()
    stats_file = memory_dir / 'automation_stats.csv'

    with open(stats_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'friendly_name', 'state', 'last_triggered', 'mode', 'currently_running'])

        for stat in stats:
            writer.writerow([
                stat['entity_id'],
                stat['friendly_name'],
                stat['state'],
                stat['last_triggered'],
                stat['mode'],
                stat['current']
            ])

    click.secho(f"✓ Automation Stats: {len(stats)} automation stats saved to automation_stats.csv", fg='green')
    return len(stats)


def sync_service_capabilities(hass_url: str, hass_token: str) -> int:
    """Sync service capabilities (available services and parameters) to memory as CSV"""
    url = f"{hass_url}/api/services"
    services_data = make_api_request(url, hass_token)

    services_list = []

    # Parse services API response (handle both list and dict formats)
    if isinstance(services_data, list):
        # List format - newer API version
        for service in services_data:
            if isinstance(service, dict):
                fields = service.get('fields', {})
                field_names = []
                required_fields = []

                for field_name, field_info in fields.items():
                    field_names.append(field_name)
                    if isinstance(field_info, dict) and field_info.get('required'):
                        required_fields.append(field_name)

                services_list.append({
                    'domain': service.get('domain', 'unknown'),
                    'service': service.get('service', 'unknown'),
                    'description': service.get('description', ''),
                    'parameters': ', '.join(field_names) if field_names else '',
                    'required_params': ', '.join(required_fields) if required_fields else ''
                })
    elif isinstance(services_data, dict):
        # Dict format - older API version
        for domain, domain_services in services_data.items():
            if isinstance(domain_services, dict):
                for service_name, service_info in domain_services.items():
                    if isinstance(service_info, dict):
                        # Extract field names and whether they're required
                        fields = service_info.get('fields', {})
                        field_names = []
                        required_fields = []

                        for field_name, field_info in fields.items():
                            field_names.append(field_name)
                            if isinstance(field_info, dict) and field_info.get('required'):
                                required_fields.append(field_name)

                        services_list.append({
                            'domain': domain,
                            'service': service_name,
                            'description': service_info.get('description', ''),
                            'parameters': ', '.join(field_names) if field_names else '',
                            'required_params': ', '.join(required_fields) if required_fields else ''
                        })
                    else:
                        # Simple service without detailed info
                        services_list.append({
                            'domain': domain,
                            'service': service_name,
                            'description': '',
                            'parameters': '',
                            'required_params': ''
                        })

    # Save to CSV
    memory_dir = ensure_memory_dir()
    services_file = memory_dir / 'service_capabilities.csv'

    with open(services_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['domain', 'service', 'description', 'parameters', 'required_params'])

        for svc in sorted(services_list, key=lambda x: (x['domain'], x['service'])):
            # Truncate description to keep CSV compact
            desc = svc['description'][:200] if svc['description'] else ''
            writer.writerow([
                svc['domain'],
                svc['service'],
                desc,
                svc['parameters'],
                svc['required_params']
            ])

    click.secho(f"✓ Service Capabilities: {len(services_list)} services saved to service_capabilities.csv", fg='green')
    return len(services_list)


def sync_battery_health(hass_url: str, hass_token: str) -> int:
    """Sync battery health information to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract battery sensors
    battery_sensors = []
    for state in states:
        entity_id = state.get('entity_id', '')
        attrs = state.get('attributes', {})

        # Check if it's a battery sensor
        if (entity_id.endswith('_battery') or
            attrs.get('device_class') == 'battery' or
            'battery' in entity_id.lower()):

            current_level = state.get('state', 'unknown')

            # Try to parse battery level as integer
            try:
                level = int(float(current_level))
            except (ValueError, TypeError):
                level = None

            # Get device info
            device_class = attrs.get('device_class', '')
            unit = attrs.get('unit_of_measurement', '')
            friendly_name = attrs.get('friendly_name', entity_id)

            battery_sensors.append({
                'entity_id': entity_id,
                'friendly_name': friendly_name,
                'current_level': current_level,
                'level_numeric': level if level is not None else '',
                'unit': unit,
                'device_class': device_class
            })

    # Save to CSV
    memory_dir = ensure_memory_dir()
    battery_file = memory_dir / 'battery_health.csv'

    with open(battery_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'friendly_name', 'current_level', 'level_numeric', 'unit', 'device_class'])

        for sensor in sorted(battery_sensors, key=lambda x: x['entity_id']):
            writer.writerow([
                sensor['entity_id'],
                sensor['friendly_name'],
                sensor['current_level'],
                sensor['level_numeric'],
                sensor['unit'],
                sensor['device_class']
            ])

    click.secho(f"✓ Battery Health: {len(battery_sensors)} battery sensors saved to battery_health.csv", fg='green')
    return len(battery_sensors)


def sync_energy_data(hass_url: str, hass_token: str) -> int:
    """Sync energy and power sensors to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    energy_sensors = []

    # Energy-related device classes
    energy_classes = ['energy', 'power', 'voltage', 'current', 'power_factor',
                     'apparent_power', 'reactive_power']

    for state in states:
        entity_id = state.get('entity_id', '')
        attrs = state.get('attributes', {})
        device_class = attrs.get('device_class', '')

        # Check if it's an energy-related sensor
        if (device_class in energy_classes or
            'energy' in entity_id.lower() or
            'power' in entity_id.lower() or
            'solar' in entity_id.lower() or
            'grid' in entity_id.lower() or
            'consumption' in entity_id.lower()):

            current_state = state.get('state', 'unknown')
            unit = attrs.get('unit_of_measurement', '')
            friendly_name = attrs.get('friendly_name', entity_id)
            state_class = attrs.get('state_class', '')

            # Categorize sensor type
            category = 'unknown'
            if 'solar' in entity_id.lower() or 'production' in entity_id.lower():
                category = 'solar_production'
            elif 'grid' in entity_id.lower() and ('import' in entity_id.lower() or 'consumption' in entity_id.lower()):
                category = 'grid_consumption'
            elif 'grid' in entity_id.lower() and 'export' in entity_id.lower():
                category = 'grid_export'
            elif device_class == 'energy':
                category = 'energy_consumption'
            elif device_class == 'power':
                category = 'power_usage'
            elif device_class in ['voltage', 'current']:
                category = 'electrical_monitoring'

            # Try to parse numeric value
            try:
                value_numeric = float(current_state)
            except (ValueError, TypeError):
                value_numeric = None

            energy_sensors.append({
                'entity_id': entity_id,
                'friendly_name': friendly_name,
                'category': category,
                'current_value': current_state,
                'value_numeric': value_numeric if value_numeric is not None else '',
                'unit': unit,
                'device_class': device_class,
                'state_class': state_class
            })

    # Save to CSV
    memory_dir = ensure_memory_dir()
    energy_file = memory_dir / 'energy_data.csv'

    with open(energy_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'friendly_name', 'category', 'current_value',
                        'value_numeric', 'unit', 'device_class', 'state_class'])

        for sensor in sorted(energy_sensors, key=lambda x: (x['category'], x['entity_id'])):
            writer.writerow([
                sensor['entity_id'],
                sensor['friendly_name'],
                sensor['category'],
                sensor['current_value'],
                sensor['value_numeric'],
                sensor['unit'],
                sensor['device_class'],
                sensor['state_class']
            ])

    click.secho(f"✓ Energy Data: {len(energy_sensors)} energy sensors saved to energy_data.csv", fg='green')
    return len(energy_sensors)


def sync_automation_context(hass_url: str, hass_token: str) -> int:
    """Sync automation context (user annotations) to memory as CSV

    This creates a template file that users can edit to add context about their automations.
    Context is preserved across syncs - only new automations are added.
    """
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    # Extract all automations
    automations = [s for s in states if s.get('entity_id', '').startswith('automation.')]

    memory_dir = ensure_memory_dir()
    context_file = memory_dir / 'automation_context.csv'

    # Load existing context if it exists
    existing_context = {}
    if context_file.exists():
        with open(context_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_context[row['entity_id']] = row

    # Merge with current automations
    context_data = []
    for auto in automations:
        entity_id = auto.get('entity_id', '')
        attrs = auto.get('attributes', {})
        friendly_name = attrs.get('friendly_name', entity_id)

        if entity_id in existing_context:
            # Keep existing context
            context_data.append(existing_context[entity_id])
        else:
            # Add new automation with empty context
            context_data.append({
                'entity_id': entity_id,
                'friendly_name': friendly_name,
                'purpose': '',
                'category': '',
                'user_notes': ''
            })

    # Save to CSV
    with open(context_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'friendly_name', 'purpose', 'category', 'user_notes'])

        for ctx in sorted(context_data, key=lambda x: x['entity_id']):
            writer.writerow([
                ctx['entity_id'],
                ctx['friendly_name'],
                ctx.get('purpose', ''),
                ctx.get('category', ''),
                ctx.get('user_notes', '')
            ])

    click.secho(f"✓ Automation Context: {len(context_data)} automations in automation_context.csv (edit to add notes)", fg='green')
    return len(context_data)


def sync_persons_presence(hass_url: str, hass_token: str) -> int:
    """Sync persons and presence detection to memory as CSV"""
    url = f"{hass_url}/api/states"
    states = make_api_request(url, hass_token)

    presence_data = []

    # Extract persons
    persons = [s for s in states if s.get('entity_id', '').startswith('person.')]
    for person in persons:
        entity_id = person.get('entity_id', '')
        attrs = person.get('attributes', {})
        current_state = person.get('state', 'unknown')

        presence_data.append({
            'entity_id': entity_id,
            'type': 'person',
            'friendly_name': attrs.get('friendly_name', entity_id),
            'state': current_state,
            'location': current_state if current_state not in ['home', 'not_home', 'unknown'] else '',
            'latitude': attrs.get('latitude', ''),
            'longitude': attrs.get('longitude', ''),
            'source': attrs.get('source', ''),
            'device_class': ''
        })

    # Extract device trackers
    trackers = [s for s in states if s.get('entity_id', '').startswith('device_tracker.')]
    for tracker in trackers:
        entity_id = tracker.get('entity_id', '')
        attrs = tracker.get('attributes', {})
        current_state = tracker.get('state', 'unknown')

        presence_data.append({
            'entity_id': entity_id,
            'type': 'device_tracker',
            'friendly_name': attrs.get('friendly_name', entity_id),
            'state': current_state,
            'location': current_state if current_state not in ['home', 'not_home', 'unknown'] else '',
            'latitude': attrs.get('latitude', ''),
            'longitude': attrs.get('longitude', ''),
            'source': attrs.get('source_type', ''),
            'device_class': ''
        })

    # Extract occupancy/presence sensors
    occupancy_sensors = [
        s for s in states
        if (s.get('entity_id', '').startswith('binary_sensor.') and
            s.get('attributes', {}).get('device_class') == 'occupancy')
    ]
    for sensor in occupancy_sensors:
        entity_id = sensor.get('entity_id', '')
        attrs = sensor.get('attributes', {})
        current_state = sensor.get('state', 'unknown')

        # Try to determine area from entity attributes
        area_id = ''
        # Check for area in attributes (entity registry mapping)
        # This would require additional API call, so we'll leave empty for now
        # Users can cross-reference with entity_relationships.csv

        presence_data.append({
            'entity_id': entity_id,
            'type': 'occupancy_sensor',
            'friendly_name': attrs.get('friendly_name', entity_id),
            'state': current_state,
            'location': '',
            'latitude': '',
            'longitude': '',
            'source': '',
            'device_class': 'occupancy'
        })

    # Save to CSV
    memory_dir = ensure_memory_dir()
    presence_file = memory_dir / 'persons_presence.csv'

    with open(presence_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_id', 'type', 'friendly_name', 'state', 'location',
                        'latitude', 'longitude', 'source', 'device_class'])

        for item in sorted(presence_data, key=lambda x: (x['type'], x['entity_id'])):
            writer.writerow([
                item['entity_id'],
                item['type'],
                item['friendly_name'],
                item['state'],
                item['location'],
                item['latitude'],
                item['longitude'],
                item['source'],
                item['device_class']
            ])

    click.secho(f"✓ Persons & Presence: {len(presence_data)} items saved to persons_presence.csv", fg='green')
    return len(presence_data)


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
