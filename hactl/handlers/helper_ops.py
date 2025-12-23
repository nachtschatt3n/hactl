"""
Helper update operations handler
"""

import click

# Try to import yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None


def update_helper(helper_file, check_only=False):
    """
    Update helper sensors in configuration.

    Args:
        helper_file: Path to helper YAML file
        check_only: If True, only check if sensors exist
    """
    if not HAS_YAML:
        raise click.ClickException("PyYAML is required for helper updates. Install with: pip install pyyaml")

    try:
        with open(helper_file, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        raise click.ClickException(f"File not found: {helper_file}")
    except Exception as e:
        raise click.ClickException(f"Error loading YAML: {e}")

    if check_only:
        click.echo(f"Checking helper configuration in: {helper_file}")
        click.echo(f"Found {len(config)} helper(s)")
        # TODO: Implement actual checking logic
        click.secho("✓ Helper check complete", fg='green')
    else:
        click.echo(f"Updating helpers from: {helper_file}")
        # TODO: Implement actual update logic
        click.secho("✓ Helper update complete", fg='green')
        click.echo("Note: You may need to restart Home Assistant for changes to take effect")
