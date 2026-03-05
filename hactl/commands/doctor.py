"""
DOCTOR command for hactl
"""

import click


@click.command('doctor')
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table',
              help='Output format')
@click.option('--check', '-c', 'check_name', default=None,
              help='Run a single check (e.g., unavailable, batteries, stale)')
def doctor_command(format, check_name):
    """Run health checks on your Home Assistant instance

    Checks API connectivity, unavailable entities, low batteries,
    error log, configuration, stale entities, automations, and
    integration status.

    Examples:

    \b
        hactl doctor
        hactl doctor --format json
        hactl doctor --check unavailable
        hactl doctor --check batteries
    """
    from hactl.handlers import doctor
    doctor.run_doctor(format_type=format, check_name=check_name)
