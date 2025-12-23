"""
Handler migrated from get/services.py
"""

import json
import click
from hactl.core import load_config, make_api_request, json_to_yaml

def get_services(format_type='table'):
    """
    Handler for services

    Args:
        format_type: Output format
    """

    # Get format from command line
    # format_type passed as parameter
    
    # Load configuration from environment
    HASS_URL, HASS_TOKEN = load_config()
    
    # Fetch services
    url = f"{HASS_URL}/api/services"
    services_data = make_api_request(url, HASS_TOKEN)
    
    # Parse services
    services_list = []
    
    # Handle both dict and list response formats
    if isinstance(services_data, list):
        # If API returns a list, it's a different format
        for service in services_data:
            if isinstance(service, dict):
                services_list.append({
                    'domain': service.get('domain', 'unknown'),
                    'service': service.get('service', 'unknown'),
                    'description': service.get('description', ''),
                    'fields': service.get('fields', {})
                })
    elif isinstance(services_data, dict):
        # Original dict format
        for domain, domain_services in services_data.items():
            if isinstance(domain_services, dict):
                for service_name, service_info in domain_services.items():
                    if isinstance(service_info, dict):
                        fields = service_info.get('fields', {})
                        service_data = {
                            'domain': domain,
                            'service': service_name,
                            'description': service_info.get('description', ''),
                            'fields': {}
                        }
                        
                        for field_name, field_info in fields.items():
                            if isinstance(field_info, dict):
                                service_data['fields'][field_name] = {
                                    'description': field_info.get('description', ''),
                                    'required': field_info.get('required', False),
                                    'example': field_info.get('example', '')
                                }
                            else:
                                service_data['fields'][field_name] = {'value': field_info}
                        
                        services_list.append(service_data)
                    else:
                        # Simple service without detailed info
                        services_list.append({
                            'domain': domain,
                            'service': service_name,
                            'description': '',
                            'fields': {}
                        })
    else:
        # Unknown format
        click.echo(f"Warning: Unexpected services API response format: {type(services_data)}", file=sys.stderr)
    
    services_list.sort(key=lambda x: (x['domain'], x['service']))
    
    # Format output
    if format_type == 'json':
        click.echo(json.dumps(services_list, indent=2))
    elif format_type == 'yaml':
        click.echo("# Home Assistant Services")
        click.echo("---")
        click.echo(json_to_yaml(services_list))
    elif format_type == 'detail':
        click.echo("=== Home Assistant Services ===\n")
        
        # Group by domain
        by_domain = {}
        for service in services_list:
            domain = service['domain']
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(service)
        
        for domain in sorted(by_domain.keys()):
            click.echo(f"## {domain.upper()} ({len(by_domain[domain])} services)\n")
            for service in by_domain[domain]:
                click.echo(f"**{service['service']}**")
                if service.get('description'):
                    click.echo(f"  - Description: {service['description']}")
                if service.get('fields'):
                    click.echo(f"  - Parameters: {', '.join(service['fields'].keys())}")
                    for field_name, field_info in service['fields'].items():
                        req_str = "required" if field_info.get('required') else "optional"
                        click.echo(f"    - {field_name} ({req_str})")
                click.echo()
    else:  # table format
        click.echo("=== Home Assistant Services ===\n")
        
        # Group by domain
        by_domain = {}
        for service in services_list:
            domain = service['domain']
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(service)
        
        for domain in sorted(by_domain.keys()):
            click.echo(f"## {domain.upper()} ({len(by_domain[domain])} services)\n")
            click.echo(f"{'Service':<30} {'Description':<50} {'Parameters':<30}")
            click.echo("-" * 110)
            for service in by_domain[domain]:
                desc = service.get('description', '') or '-'
                if len(desc) > 48:
                    desc = desc[:45] + '...'
                params = ', '.join(service.get('fields', {}).keys()) or '-'
                if len(params) > 28:
                    params = params[:25] + '...'
                click.echo(f"{service['service']:<30} {desc:<50} {params:<30}")
            click.echo()


