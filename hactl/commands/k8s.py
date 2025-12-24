"""
K8S command group for hactl
"""

import click


@click.group('k8s')
def k8s_group():
    """Kubernetes configuration management"""
    pass


@k8s_group.command('update-config')
@click.argument('helper_file', type=click.Path(exists=True))
@click.option('--namespace', '-n', default='home-automation', help='Kubernetes namespace')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def k8s_update_config(helper_file, namespace, dry_run):
    """Update Home Assistant config via kubectl

    This command finds the Home Assistant pod and updates
    configuration.yaml with helper sensors from the YAML file.

    Examples:

    \b
        hactl k8s update-config battery-summary.yaml
        hactl k8s update-config battery-summary.yaml --namespace home-automation
        hactl k8s update-config battery-summary.yaml --dry-run
    """
    from hactl.handlers import k8s_config
    k8s_config.update_config(helper_file, namespace=namespace, dry_run=dry_run)


@k8s_group.command('find-pod')
@click.option('--namespace', '-n', default='home-automation', help='Kubernetes namespace')
def k8s_find_pod(namespace):
    """Find Home Assistant pod in Kubernetes

    Examples:

    \b
        hactl k8s find-pod
        hactl k8s find-pod --namespace home-automation
    """
    from hactl.handlers import k8s_config
    k8s_config.find_pod(namespace=namespace)


@k8s_group.command('get-config')
@click.option('--namespace', '-n', default='home-automation', help='Kubernetes namespace')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
@click.option('--file', '-f', default='/config/configuration.yaml', help='Config file path in pod')
def k8s_get_config(namespace, output, file):
    """Get Home Assistant configuration from Kubernetes pod

    Examples:

    \b
        hactl k8s get-config
        hactl k8s get-config --output config.yaml
        hactl k8s get-config --file /config/templates.yaml
    """
    from hactl.handlers import k8s_config
    k8s_config.get_config(namespace=namespace, output_file=output, config_file=file)


@k8s_group.command('put-config')
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--namespace', '-n', default='home-automation', help='Kubernetes namespace')
@click.option('--file', '-f', default='/config/configuration.yaml', help='Config file path in pod')
@click.option('--backup/--no-backup', default=True, help='Create backup before updating')
@click.option('--restart/--no-restart', default=True, help='Restart Home Assistant after update')
def k8s_put_config(input_file, namespace, file, backup, restart):
    """Upload configuration to Home Assistant pod

    Examples:

    \b
        hactl k8s put-config config.yaml
        hactl k8s put-config templates.yaml --file /config/templates.yaml
        hactl k8s put-config config.yaml --no-restart
    """
    from hactl.handlers import k8s_config
    k8s_config.put_config(input_file, namespace=namespace, config_file=file,
                          backup=backup, restart=restart)
