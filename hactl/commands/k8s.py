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
