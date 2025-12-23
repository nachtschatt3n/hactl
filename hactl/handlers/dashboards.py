"""
Handler migrated from get/dashboards.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_dashboards(format_type='table'):
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
        # Output single dashboard YAML (specify with DASHBOARD_URL_PATH env var)
        target_path = os.environ.get('DASHBOARD_URL_PATH', 'lovelace')
        if target_path in configs:
            cfg = configs[target_path]
            yaml_output = json_to_yaml(cfg)
            click.echo(yaml_output)
        else:
            click.echo(f"# Dashboard config not found for: {target_path}", file=sys.stderr)
            return
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


