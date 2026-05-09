"""
AI content generation handler for hactl
"""

import json
import datetime
from pathlib import Path

import click

GENERATED_DIR = Path(__file__).parent.parent.parent / 'generated'

_TEMPLATES = {
    'dashboard': """\
title: {title}
views:
  - title: Home
    path: home
    cards: []
""",
    'automation': """\
alias: {title}
description: ''
trigger: []
condition: []
action: []
mode: single
""",
    'blueprint': """\
blueprint:
  name: {title}
  description: ''
  domain: automation
  input: {{}}
trigger: []
action: []
""",
    'script': """\
{slug}:
  alias: {title}
  sequence: []
  mode: single
""",
}


def _slugify(text: str) -> str:
    return text.lower().replace(' ', '_').replace('-', '_')


def _write_manifest(category_dir: Path, filename: str) -> None:
    manifest_file = category_dir / 'manifest.json'
    if manifest_file.exists():
        with open(manifest_file) as f:
            manifest = json.load(f)
    else:
        manifest = {'files': []}
    manifest['files'].append({
        'filename': filename,
        'created': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'applied': False,
    })
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)


def generate_content(content_type: str, description: str) -> None:
    slug = _slugify(description)
    category = content_type + 's'
    category_dir = GENERATED_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)

    filename = f'{slug}.yaml'
    output_path = category_dir / filename
    content = _TEMPLATES[content_type].format(title=description, slug=slug)
    output_path.write_text(content)

    _write_manifest(category_dir, filename)
    click.echo(f'Generated {content_type}: {output_path}')


def list_generated(category: str = None) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    click.echo('Generated Content:')
    categories = [category] if category else ['dashboards', 'automations', 'blueprints', 'scripts']
    for cat in categories:
        cat_dir = GENERATED_DIR / cat
        header = cat.capitalize() + ':'
        if not cat_dir.exists():
            click.echo(f'  {header} (none)')
            continue
        files = list(cat_dir.glob('*.yaml'))
        click.echo(f'  {header}')
        for f in files:
            click.echo(f'    {f.name}')
        if not files:
            click.echo('    (none)')


def apply_generated(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        raise click.ClickException(f'File not found: {file_path}')

    parts = path.parts
    if 'dashboards' in parts:
        content_type = 'dashboard'
    elif 'automations' in parts:
        content_type = 'automation'
    elif 'blueprints' in parts:
        content_type = 'blueprint'
    elif 'scripts' in parts:
        content_type = 'script'
    else:
        content_type = 'file'

    manifest_file = path.parent / 'manifest.json'
    if manifest_file.exists():
        with open(manifest_file) as f:
            manifest = json.load(f)
        for entry in manifest.get('files', []):
            if entry['filename'] == path.name:
                entry['applied'] = True
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)

    click.echo(f'Applied {content_type}: {path.name}')
    click.echo(f'  Source: {path}')
    click.echo('  Note: manually copy this YAML into Home Assistant to apply it.')
