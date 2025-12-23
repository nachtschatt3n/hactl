"""
Kubernetes configuration operations handler
"""

import subprocess
import click


def run_kubectl(cmd, namespace="home-automation"):
    """Run kubectl command"""
    full_cmd = f"kubectl {cmd} -n {namespace}"
    try:
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"kubectl error: {e.stderr}")


def find_hass_pod(namespace="home-automation"):
    """Find Home Assistant pod"""
    pods = run_kubectl("get pods -o jsonpath='{.items[*].metadata.name}'", namespace)
    if not pods:
        return None

    for pod in pods.split():
        if 'home-assistant' in pod.lower() and 'esphome' not in pod.lower():
            return pod
    return None


def find_pod(namespace="home-automation"):
    """Find and display Home Assistant pod"""
    click.echo(f"Finding Home Assistant pod in namespace: {namespace}")

    pod = find_hass_pod(namespace)
    if pod:
        click.secho(f"✓ Found pod: {pod}", fg='green')

        # Get pod status
        status = run_kubectl(f"get pod {pod} -o jsonpath='{{.status.phase}}'", namespace)
        click.echo(f"  Status: {status}")

        # Get pod age
        age = run_kubectl(f"get pod {pod} -o jsonpath='{{.metadata.creationTimestamp}}'", namespace)
        click.echo(f"  Created: {age}")
    else:
        click.secho("✗ No Home Assistant pod found", fg='red')


def update_config(helper_file, namespace="home-automation", dry_run=False):
    """
    Update Home Assistant configuration via kubectl.

    Args:
        helper_file: Path to helper YAML file
        namespace: Kubernetes namespace
        dry_run: If True, show what would be done
    """
    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made\n", fg='yellow')

    click.echo(f"Updating Home Assistant config in namespace: {namespace}")
    click.echo(f"Helper file: {helper_file}\n")

    # Find pod
    pod = find_hass_pod(namespace)
    if not pod:
        raise click.ClickException("No Home Assistant pod found")

    click.secho(f"✓ Found pod: {pod}", fg='green')

    # Find config path
    config_path = '/config/configuration.yaml'
    click.echo(f"  Config path: {config_path}")

    if dry_run:
        click.echo("\nWould perform:")
        click.echo(f"  1. Backup {config_path}")
        click.echo(f"  2. Read current config from pod")
        click.echo(f"  3. Merge helpers from {helper_file}")
        click.echo(f"  4. Write updated config to pod")
        click.echo(f"  5. Reload Home Assistant configuration")
        click.secho("\n✓ Dry run complete - no changes made", fg='green')
    else:
        click.echo("\nTODO: Implement config update logic")
        click.secho("⚠ Not yet implemented", fg='yellow')
        click.echo("\nManual steps:")
        click.echo(f"  1. kubectl -n {namespace} exec {pod} -- cat /config/configuration.yaml > config.yaml")
        click.echo(f"  2. Edit config.yaml to add helpers from {helper_file}")
        click.echo(f"  3. kubectl -n {namespace} cp config.yaml {pod}:/config/configuration.yaml")
        click.echo(f"  4. kubectl -n {namespace} exec {pod} -- ha core restart")
