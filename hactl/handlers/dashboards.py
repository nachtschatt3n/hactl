"""
Handler migrated from get/dashboards.py
"""

import os
import sys
import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml
from hactl.core.websocket import WebSocketClient

def get_dashboards(format_type='table', url_path=None, output_dir=None):
    """
    Handler for dashboards

    Args:
        format_type: Output format
    """

    # Get format from command line
    # format_type passed as parameter
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Connect to WebSocket
    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()
        
        # Get panels
        panels = ws.call("get_panels")
        dashboards = []
        
        if isinstance(panels, dict):
            seen_paths = set()
            for key, panel in panels.items():
                if isinstance(panel, dict) and panel.get("component_name") == "lovelace":
                    path = panel.get("url_path") or key
                    if path == "lovelace":
                        continue  # default alias that does not expose config
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
                    dashboards.append({
                        "id": panel.get("config_panel", key),
                        "title": panel.get("title", key.title()),
                        "url_path": path,
                        "icon": panel.get("icon")
                    })
        
        if not dashboards:
            dashboards = [{"id": "default", "title": "Home", "url_path": "lovelace"}]
        
        # Get dashboard configs
        results = []
        configs = {}
        
        for dash in dashboards:
            try:
                cfg = ws.call("lovelace/config", url_path=dash.get('url_path', 'lovelace'))
                configs[dash.get('url_path', 'lovelace')] = cfg
            except RuntimeError as err:
                results.append({
                    'title': dash.get('title', dash.get('id')),
                    'url_path': dash.get('url_path', 'lovelace'),
                    'error': str(err)
                })
                continue
            
            views = cfg.get('views', []) if isinstance(cfg, dict) else []
            dash_summary = {
                'title': dash.get('title', dash.get('id')),
                'url_path': dash.get('url_path', 'lovelace'),
                'mode': cfg.get('mode') if isinstance(cfg, dict) else dash.get('mode'),
                'strategy': cfg.get('strategy'),
                'views': []
            }
            
            for idx, view in enumerate(views):
                cards = []
                if isinstance(view.get('cards'), list):
                    cards.extend(view['cards'])
                if isinstance(view.get('sections'), list):
                    for section in view['sections']:
                        cards.extend(section.get('cards', []))
                
                dash_summary['views'].append({
                    'index': idx,
                    'title': view.get('title', f'View {idx+1}'),
                    'path': view.get('path'),
                    'icon': view.get('icon'),
                    'badges': len(view.get('badges', [])),
                    'cards': [
                        {
                            'type': card.get('type', 'unknown'),
                            'title': card.get('title'),
                            'entities': len(card.get('entities', [])) if isinstance(card.get('entities'), list) else None
                        }
                        for card in cards
                    ]
                })
            results.append(dash_summary)
    
    finally:
        ws.close()
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(results, indent=2))
    elif format_type == 'yaml':
        # Output YAML configs for each dashboard
        for dash in dashboards:
            url_path = dash.get('url_path', 'lovelace')
            title = dash.get('title', dash.get('id', 'Unknown'))
            if url_path in configs:
                click.echo(f"# Dashboard: {title} (/{url_path})")
                click.echo(f"# URL: {HASS_URL}/{url_path}")
                click.echo("---")
                cfg = configs[url_path]
                yaml_output = json_to_yaml(cfg)
                click.echo(yaml_output)
                click.echo("\n")
            else:
                click.echo(f"# Dashboard: {title} (/{url_path}) - Config not available")
                click.echo("---\n")
    elif format_type == 'yaml-save':
        # Save each dashboard YAML to a file
        if output_dir is None:
            output_dir = os.environ.get('DASHBOARD_OUTPUT_DIR', '.')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        for dash in dashboards:
            url_path = dash.get('url_path', 'lovelace')
            title = dash.get('title', dash.get('id', 'Unknown'))
            if url_path in configs:
                # Sanitize filename
                safe_name = "".join(c for c in url_path if c.isalnum() or c in ('-', '_')).strip()
                filename = os.path.join(output_dir, f"{safe_name}.yaml")
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"# Dashboard: {title} (/{url_path})\n")
                    f.write(f"# URL: {HASS_URL}/{url_path}\n")
                    f.write("# Generated by get/dashboards.py\n")
                    f.write("---\n")
                    cfg = configs[url_path]
                    yaml_output = json_to_yaml(cfg)
                    f.write(yaml_output)
                click.echo(f"Saved: {filename}")
            else:
                click.echo(f"Skipped: {title} (/{url_path}) - Config not available", file=sys.stderr)
    elif format_type == 'yaml-single':
        # Output single dashboard YAML (specify with url_path parameter)
        # Support view paths: light-control/battery-monitor
        target_path = url_path or os.environ.get('DASHBOARD_URL_PATH', 'lovelace')

        # Check if it's a view path (contains /)
        if '/' in target_path:
            dashboard_path, view_path = target_path.split('/', 1)

            if dashboard_path in configs:
                cfg = configs[dashboard_path]

                # Extract specific view
                views = cfg.get('views', [])
                found_view = None
                for view in views:
                    if view.get('path') == view_path:
                        found_view = view
                        break

                if found_view:
                    click.echo(f"# View: {found_view.get('title', view_path)}")
                    click.echo(f"# Dashboard: {dashboard_path}")
                    click.echo(f"# Path: {target_path}")
                    click.echo("---")
                    yaml_output = json_to_yaml(found_view)
                    click.echo(yaml_output)
                else:
                    click.echo(f"# View '{view_path}' not found in dashboard '{dashboard_path}'", file=sys.stderr)
                    click.echo(f"# Available views:", file=sys.stderr)
                    for view in views:
                        click.echo(f"#   - {view.get('path', 'N/A')}: {view.get('title', 'Untitled')}", file=sys.stderr)
                    return
            else:
                click.echo(f"# Dashboard '{dashboard_path}' not found", file=sys.stderr)
                return
        else:
            # Regular dashboard path
            if target_path in configs:
                cfg = configs[target_path]
                yaml_output = json_to_yaml(cfg)
                click.echo(yaml_output)
            else:
                click.echo(f"# Dashboard config not found for: {target_path}", file=sys.stderr)
                return
    elif format_type == 'validate':
        # Validate dashboard/view entities against memory/states.csv
        import csv
        from pathlib import Path

        target_path = url_path or os.environ.get('DASHBOARD_URL_PATH', 'lovelace')

        # Get the config to validate
        config_to_validate = None
        display_name = target_path

        if '/' in target_path:
            dashboard_path, view_path = target_path.split('/', 1)
            if dashboard_path in configs:
                cfg = configs[dashboard_path]
                views = cfg.get('views', [])
                for view in views:
                    if view.get('path') == view_path:
                        config_to_validate = view
                        display_name = f"{view.get('title', view_path)} ({target_path})"
                        break
                if not config_to_validate:
                    click.echo(f"Error: View '{view_path}' not found in dashboard '{dashboard_path}'", file=sys.stderr)
                    return
            else:
                click.echo(f"Error: Dashboard '{dashboard_path}' not found", file=sys.stderr)
                return
        else:
            if target_path in configs:
                config_to_validate = configs[target_path]
                display_name = f"Dashboard: {target_path}"
            else:
                click.echo(f"Error: Dashboard '{target_path}' not found", file=sys.stderr)
                return

        # Extract all entities from the config
        def extract_entities(obj, entities=None):
            """Recursively extract entity IDs from a config object"""
            if entities is None:
                entities = set()

            if isinstance(obj, dict):
                # Check for entity field
                if 'entity' in obj and isinstance(obj['entity'], str):
                    entities.add(obj['entity'])
                # Check for entities list
                if 'entities' in obj:
                    if isinstance(obj['entities'], list):
                        for ent in obj['entities']:
                            if isinstance(ent, str):
                                entities.add(ent)
                            elif isinstance(ent, dict):
                                extract_entities(ent, entities)
                # Recurse into all dict values
                for value in obj.values():
                    extract_entities(value, entities)
            elif isinstance(obj, list):
                for item in obj:
                    extract_entities(item, entities)

            return entities

        dashboard_entities = extract_entities(config_to_validate)

        # Load memory/states.csv
        memory_dir = Path.cwd() / 'memory'
        states_csv = memory_dir / 'states.csv'

        if not states_csv.exists():
            click.echo("Warning: memory/states.csv not found. Run 'hactl memory sync' first.", file=sys.stderr)
            click.echo(f"\nFound {len(dashboard_entities)} entities in config (cannot validate):")
            for entity in sorted(dashboard_entities):
                click.echo(f"  - {entity}")
            return

        # Load existing entities
        existing_entities = {}
        with open(states_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entity_id = row['entity_id']
                existing_entities[entity_id] = {
                    'friendly_name': row['friendly_name'],
                    'domain': row['domain']
                }

        # Check which entities are missing
        missing = []
        valid = []
        for entity in dashboard_entities:
            if entity in existing_entities:
                valid.append(entity)
            else:
                missing.append(entity)

        # Output validation report
        click.echo(f"=== Validating: {display_name} ===")
        click.echo(f"Total entities: {len(dashboard_entities)}")
        click.secho(f"✓ Valid: {len(valid)}", fg='green')

        if missing:
            click.secho(f"✗ Missing: {len(missing)}", fg='red')
            click.echo("\nMissing entities:")

            # Find suggestions for each missing entity
            for missing_entity in sorted(missing):
                click.echo(f"  - {missing_entity}")

                # Try to find similar entities
                domain = missing_entity.split('.')[0] if '.' in missing_entity else ''
                name_part = missing_entity.split('.')[1] if '.' in missing_entity else missing_entity

                # Find entities in same domain with similar names
                suggestions = []
                for entity_id, info in existing_entities.items():
                    if info['domain'] == domain:
                        # Check if name is similar
                        entity_name = entity_id.split('.')[1] if '.' in entity_id else entity_id
                        if name_part.lower() in entity_name.lower() or entity_name.lower() in name_part.lower():
                            suggestions.append((entity_id, info['friendly_name']))

                if suggestions:
                    click.echo(f"    Suggestions:")
                    for sugg_id, sugg_name in suggestions[:3]:
                        click.echo(f"      → {sugg_id} ({sugg_name})")
        else:
            click.secho("✓ All entities valid!", fg='green')
    elif format_type == 'detail':
        for dash in results:
            click.echo(f"Dashboard: {dash['title']} (/{dash['url_path']}) mode={dash.get('mode','')} views={len(dash['views'])}")
            for view in dash['views']:
                click.echo(f"  View {view['index']+1}: {view['title']} (path={view.get('path')}, icon={view.get('icon')})")
                click.echo(f"    Badges: {view['badges']}  Cards: {len(view['cards'])}")
                for card in view['cards'][:5]:
                    ent_info = f", entities={card['entities']}" if card['entities'] is not None else ''
                    click.echo(f"      - {card['type']} {card.get('title') or ''}{ent_info}")
            click.echo()
    else:  # table format
        click.echo("=== Home Assistant Dashboards ===")
        for dash in results:
            click.echo(f"Dashboard: {dash['title']} (/{dash['url_path']})  Views: {len(dash['views'])}")
            for view in dash['views'][:5]:
                cards = len(view['cards'])
                sample_titles = [c.get('title') for c in view['cards'] if c.get('title')]
                sample = ', '.join(sample_titles[:3]) if sample_titles else 'Untitled cards'
                if len(sample) > 80:
                    sample = sample[:77] + '…'
                click.echo(f"  - {view['title']} (cards={cards}) e.g., {sample}")
            if len(dash['views']) > 5:
                click.echo(f"    … {len(dash['views'])-5} more views")
            click.echo()


