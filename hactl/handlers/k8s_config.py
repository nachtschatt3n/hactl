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


def get_config(namespace="home-automation", output_file=None, config_file="/config/configuration.yaml"):
    """
    Get configuration file from Home Assistant pod.

    Args:
        namespace: Kubernetes namespace
        output_file: Local file to save to (None = stdout)
        config_file: Path to config file in pod
    """
    pod = find_hass_pod(namespace)
    if not pod:
        raise click.ClickException("No Home Assistant pod found")

    click.echo(f"Downloading {config_file} from pod {pod}...", err=True)

    try:
        # Read file from pod
        result = subprocess.run(
            f"kubectl -n {namespace} exec {pod} -- cat {config_file}",
            shell=True, capture_output=True, text=True, check=True
        )
        content = result.stdout

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            click.secho(f"✓ Saved to {output_file}", fg='green', err=True)
        else:
            click.echo(content)

    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Failed to read config: {e.stderr}")


def put_config(input_file, namespace="home-automation", config_file="/config/configuration.yaml",
               backup=True, restart=True):
    """
    Upload configuration file to Home Assistant pod.

    Args:
        input_file: Local file to upload
        namespace: Kubernetes namespace
        config_file: Path to config file in pod
        backup: Create backup before updating
        restart: Restart Home Assistant after update
    """
    import os
    import tempfile
    from datetime import datetime

    pod = find_hass_pod(namespace)
    if not pod:
        raise click.ClickException("No Home Assistant pod found")

    click.echo(f"Uploading {input_file} to pod {pod}:{config_file}")

    # Create backup if requested
    if backup:
        backup_name = f"{config_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        click.echo(f"Creating backup: {backup_name}")
        try:
            subprocess.run(
                f"kubectl -n {namespace} exec {pod} -- cp {config_file} {backup_name}",
                shell=True, capture_output=True, text=True, check=True
            )
            click.secho(f"✓ Backup created", fg='green')
        except subprocess.CalledProcessError as e:
            click.secho(f"⚠ Backup failed: {e.stderr}", fg='yellow')

    # Upload file
    try:
        subprocess.run(
            f"kubectl -n {namespace} cp {input_file} {pod}:{config_file}",
            shell=True, capture_output=True, text=True, check=True
        )
        click.secho(f"✓ File uploaded", fg='green')
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Upload failed: {e.stderr}")

    # Restart if requested
    if restart:
        click.echo("Restarting Home Assistant...")
        try:
            subprocess.run(
                f"kubectl -n {namespace} exec {pod} -- ha core restart",
                shell=True, capture_output=True, text=True, check=True
            )
            click.secho("✓ Restart initiated", fg='green')
            click.echo("Note: Home Assistant will be unavailable for ~30 seconds")
        except subprocess.CalledProcessError as e:
            click.secho(f"⚠ Restart command failed: {e.stderr}", fg='yellow')


def update_config(helper_file, namespace="home-automation", dry_run=False):
    """
    Update Home Assistant configuration via kubectl.

    Args:
        helper_file: Path to helper YAML file
        namespace: Kubernetes namespace
        dry_run: If True, show what would be done
    """
    import tempfile
    import os

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made\n", fg='yellow')

    click.echo(f"Updating Home Assistant config in namespace: {namespace}")
    click.echo(f"Helper file: {helper_file}\n")

    # Find pod
    pod = find_hass_pod(namespace)
    if not pod:
        raise click.ClickException("No Home Assistant pod found")

    click.secho(f"✓ Found pod: {pod}", fg='green')

    # Config path
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
        return

    # Read helper file
    try:
        with open(helper_file, 'r', encoding='utf-8') as f:
            helper_content = f.read()
    except Exception as e:
        raise click.ClickException(f"Failed to read helper file: {e}")

    # Download current config
    click.echo("\n1. Downloading current configuration...")
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.yaml', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        get_config(namespace=namespace, output_file=tmp_path, config_file=config_path)

        # Read current config
        with open(tmp_path, 'r', encoding='utf-8') as f:
            current_config = f.read()

        # Simple merge: add template section if not present
        click.echo("\n2. Merging helper configuration...")

        if 'template:' in current_config:
            click.echo("   Config already has template: section")
            click.echo("   Manual merge required - use 'hactl k8s get-config' and edit manually")
            raise click.ClickException("Template section already exists - manual merge required")

        # Append helper content
        updated_config = current_config.rstrip() + "\n\n# Added by hactl\ntemplate:\n" + helper_content

        # Write updated config
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(updated_config)

        click.secho("✓ Configuration merged", fg='green')

        # Upload and restart
        click.echo("\n3. Uploading updated configuration...")
        put_config(tmp_path, namespace=namespace, config_file=config_path, backup=True, restart=True)

        click.secho("\n✓ Configuration update complete!", fg='green')

    finally:
        # Cleanup temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
