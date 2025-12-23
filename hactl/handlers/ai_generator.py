"""
AI-assisted generation utilities
"""

import os
import json
import yaml
import click
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


# Base generated directory
GENERATED_DIR = Path(__file__).parent.parent.parent / 'generated'


def ensure_generated_dir(category: str) -> Path:
    """Ensure generated directory exists"""
    path = GENERATED_DIR / category
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_manifest(category: str) -> Dict[str, Any]:
    """Load manifest file for a category"""
    manifest_file = GENERATED_DIR / category / 'manifest.json'

    if manifest_file.exists():
        with open(manifest_file, 'r') as f:
            return json.load(f)
    else:
        return {'files': []}


def save_manifest(category: str, manifest: Dict[str, Any]):
    """Save manifest file for a category"""
    ensure_generated_dir(category)
    manifest_file = GENERATED_DIR / category / 'manifest.json'

    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)


def generate_filename(category: str, description: str) -> str:
    """Generate timestamped filename"""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    # Clean description for filename
    clean_desc = description.lower().replace(' ', '_')[:50]
    return f"{timestamp}_{clean_desc}.yaml"


def load_memory_context() -> Dict[str, Any]:
    """Load AI context from memory directory"""
    memory_dir = Path(__file__).parent.parent.parent / 'memory'
    context = {}

    # Load preferences if exists
    preferences_file = memory_dir / 'context' / 'preferences.md'
    if preferences_file.exists():
        context['preferences'] = preferences_file.read_text()

    # Load AI instructions if exists
    instructions_file = memory_dir / 'context' / 'ai_instructions.md'
    if instructions_file.exists():
        context['instructions'] = instructions_file.read_text()

    # Load devices
    devices_file = memory_dir / 'devices' / 'devices.json'
    if devices_file.exists():
        with open(devices_file, 'r') as f:
            context['devices'] = json.load(f)

    # Load sensors
    sensors_file = memory_dir / 'sensors' / 'sensors.json'
    if sensors_file.exists():
        with open(sensors_file, 'r') as f:
            context['sensors'] = json.load(f)

    return context


def generate_dashboard(description: str, use_template: bool = True) -> str:
    """
    Generate dashboard YAML from description.

    Args:
        description: User description of desired dashboard
        use_template: Use template-based generation (default: True)

    Returns:
        Path to generated file
    """
    click.echo(f"Generating dashboard: {description}")

    # Load context
    context = load_memory_context()

    # For now, use template-based generation
    if use_template:
        dashboard_yaml = generate_dashboard_template(description, context)
    else:
        click.secho("AI-based generation not yet implemented", fg='yellow')
        dashboard_yaml = generate_dashboard_template(description, context)

    # Save to generated directory
    category_dir = ensure_generated_dir('dashboards')
    filename = generate_filename('dashboards', description)
    filepath = category_dir / filename

    with open(filepath, 'w') as f:
        f.write(dashboard_yaml)

    # Update manifest
    manifest = load_manifest('dashboards')
    manifest['files'].append({
        'filename': filename,
        'created': datetime.now().isoformat(),
        'description': description,
        'applied': False,
        'applied_date': None
    })
    save_manifest('dashboards', manifest)

    click.secho(f"✓ Generated dashboard: {filepath}", fg='green')
    click.echo(f"\nReview the file and apply with:")
    click.echo(f"  hactl generate apply {filepath}")

    return str(filepath)


def generate_dashboard_template(description: str, context: Dict[str, Any]) -> str:
    """Generate dashboard using template"""
    template = {
        'title': description.title(),
        'views': [
            {
                'title': 'Overview',
                'path': 'overview',
                'cards': [
                    {
                        'type': 'markdown',
                        'content': f'# {description.title()}\n\nGenerated dashboard based on: {description}'
                    },
                    {
                        'type': 'entities',
                        'title': 'Entities',
                        'entities': []
                    }
                ]
            }
        ]
    }

    # Add some sensors if available
    if 'sensors' in context:
        sensors = context['sensors'][:5]  # First 5 sensors
        for sensor in sensors:
            template['views'][0]['cards'][1]['entities'].append(sensor['entity_id'])

    return yaml.dump(template, default_flow_style=False, sort_keys=False)


def generate_automation(description: str) -> str:
    """
    Generate automation YAML from description.

    Args:
        description: User description of desired automation

    Returns:
        Path to generated file
    """
    click.echo(f"Generating automation: {description}")

    # Load context
    context = load_memory_context()

    # Use template-based generation
    automation_yaml = generate_automation_template(description, context)

    # Save to generated directory
    category_dir = ensure_generated_dir('automations')
    filename = generate_filename('automations', description)
    filepath = category_dir / filename

    with open(filepath, 'w') as f:
        f.write(automation_yaml)

    # Update manifest
    manifest = load_manifest('automations')
    manifest['files'].append({
        'filename': filename,
        'created': datetime.now().isoformat(),
        'description': description,
        'applied': False,
        'applied_date': None
    })
    save_manifest('automations', manifest)

    click.secho(f"✓ Generated automation: {filepath}", fg='green')
    click.echo(f"\nReview the file and apply with:")
    click.echo(f"  hactl generate apply {filepath}")

    return str(filepath)


def generate_automation_template(description: str, context: Dict[str, Any]) -> str:
    """Generate automation using template"""
    template = {
        'alias': description,
        'description': f'Auto-generated: {description}',
        'trigger': [
            {
                'platform': 'state',
                'entity_id': 'binary_sensor.example'
            }
        ],
        'condition': [],
        'action': [
            {
                'service': 'notify.notify',
                'data': {
                    'message': f'Automation triggered: {description}'
                }
            }
        ],
        'mode': 'single'
    }

    return yaml.dump(template, default_flow_style=False, sort_keys=False)


def generate_blueprint(description: str) -> str:
    """
    Generate blueprint YAML from description.

    Args:
        description: User description of desired blueprint

    Returns:
        Path to generated file
    """
    click.echo(f"Generating blueprint: {description}")

    # Use template-based generation
    blueprint_yaml = generate_blueprint_template(description)

    # Save to generated directory
    category_dir = ensure_generated_dir('blueprints')
    filename = generate_filename('blueprints', description)
    filepath = category_dir / filename

    with open(filepath, 'w') as f:
        f.write(blueprint_yaml)

    # Update manifest
    manifest = load_manifest('blueprints')
    manifest['files'].append({
        'filename': filename,
        'created': datetime.now().isoformat(),
        'description': description,
        'applied': False,
        'applied_date': None
    })
    save_manifest('blueprints', manifest)

    click.secho(f"✓ Generated blueprint: {filepath}", fg='green')

    return str(filepath)


def generate_blueprint_template(description: str) -> str:
    """Generate blueprint using template"""
    template = {
        'blueprint': {
            'name': description,
            'description': f'Auto-generated blueprint: {description}',
            'domain': 'automation',
            'input': {
                'trigger_entity': {
                    'name': 'Trigger Entity',
                    'selector': {
                        'entity': {}
                    }
                },
                'action_device': {
                    'name': 'Action Device',
                    'selector': {
                        'device': {}
                    }
                }
            }
        },
        'trigger': [
            {
                'platform': 'state',
                'entity_id': '!input trigger_entity'
            }
        ],
        'action': [
            {
                'device_id': '!input action_device',
                'domain': 'light',
                'type': 'turn_on'
            }
        ]
    }

    return yaml.dump(template, default_flow_style=False, sort_keys=False)


def generate_script(description: str) -> str:
    """
    Generate script YAML from description.

    Args:
        description: User description of desired script

    Returns:
        Path to generated file
    """
    click.echo(f"Generating script: {description}")

    # Use template-based generation
    script_yaml = generate_script_template(description)

    # Save to generated directory
    category_dir = ensure_generated_dir('scripts')
    filename = generate_filename('scripts', description)
    filepath = category_dir / filename

    with open(filepath, 'w') as f:
        f.write(script_yaml)

    # Update manifest
    manifest = load_manifest('scripts')
    manifest['files'].append({
        'filename': filename,
        'created': datetime.now().isoformat(),
        'description': description,
        'applied': False,
        'applied_date': None
    })
    save_manifest('scripts', manifest)

    click.secho(f"✓ Generated script: {filepath}", fg='green')
    click.echo(f"\nReview the file and apply with:")
    click.echo(f"  hactl generate apply {filepath}")

    return str(filepath)


def generate_script_template(description: str) -> str:
    """Generate script using template"""
    template = {
        'alias': description,
        'sequence': [
            {
                'service': 'notify.notify',
                'data': {
                    'message': f'Script executed: {description}'
                }
            }
        ]
    }

    return yaml.dump(template, default_flow_style=False, sort_keys=False)


def list_generated(category: Optional[str] = None):
    """
    List all generated content.

    Args:
        category: Optional category filter (dashboards, automations, blueprints, scripts)
    """
    categories = [category] if category else ['dashboards', 'automations', 'blueprints', 'scripts']

    click.secho("Generated Content:", fg='green')
    click.echo()

    for cat in categories:
        manifest = load_manifest(cat)
        files = manifest.get('files', [])

        click.secho(f"{cat.title()}:", fg='cyan')
        if not files:
            click.echo("  (none)")
        else:
            for file_entry in files:
                filename = file_entry['filename']
                description = file_entry['description']
                created = file_entry['created']
                applied = "✓ Applied" if file_entry['applied'] else "Not applied"

                click.echo(f"  {filename}")
                click.echo(f"    Description: {description}")
                click.echo(f"    Created: {created}")
                click.echo(f"    Status: {applied}")
        click.echo()


def apply_generated(file_path: str):
    """
    Apply generated content to Home Assistant.

    Args:
        file_path: Path to generated YAML file
    """
    filepath = Path(file_path)

    if not filepath.exists():
        raise click.ClickException(f"File not found: {file_path}")

    # Determine category from path
    if 'dashboards' in str(filepath):
        category = 'dashboards'
    elif 'automations' in str(filepath):
        category = 'automations'
    elif 'blueprints' in str(filepath):
        category = 'blueprints'
    elif 'scripts' in str(filepath):
        category = 'scripts'
    else:
        raise click.ClickException("Cannot determine category from file path")

    click.echo(f"Applying {category[:-1]}: {filepath.name}")

    if category == 'dashboards':
        # Use dashboard update command
        click.echo("\nTo apply this dashboard, use:")
        click.echo(f"  hactl update dashboard <url_path> --from {filepath}")
        click.secho("\n⚠ Manual application required for dashboards", fg='yellow')
    else:
        click.echo("\nTo apply this configuration:")
        click.echo("  1. Review the YAML file")
        click.echo("  2. Copy to your Home Assistant configuration directory")
        click.echo("  3. Reload the appropriate integration")
        click.secho("\n⚠ Manual application required", fg='yellow')

    # Mark as applied in manifest
    manifest = load_manifest(category)
    for file_entry in manifest.get('files', []):
        if file_entry['filename'] == filepath.name:
            file_entry['applied'] = True
            file_entry['applied_date'] = datetime.now().isoformat()
            break

    save_manifest(category, manifest)
    click.secho(f"\n✓ Marked as applied in manifest", fg='green')
