"""
Generate command group for hactl
"""

import click


@click.group('generate')
def generate_group():
    """AI-assisted generation of dashboards, automations, and blueprints"""
    pass


@generate_group.command('dashboard')
@click.argument('description')
@click.option('--template/--ai', default=True, help='Use template-based generation (default) or AI')
def generate_dashboard(description, template):
    """Generate dashboard YAML from description

    Uses AI context from memory/ directory to generate a dashboard
    that matches your preferences and available devices.

    Examples:

    \b
        hactl generate dashboard "energy monitoring with solar panels"
        hactl generate dashboard "bedroom climate control"
        hactl generate dashboard "security overview with cameras"
    """
    from hactl.handlers import ai_generator
    ai_generator.generate_dashboard(description, use_template=template)


@generate_group.command('automation')
@click.argument('description')
def generate_automation(description):
    """Generate automation YAML from description

    Uses AI context from memory/ directory to generate an automation
    that follows your preferences and naming conventions.

    Examples:

    \b
        hactl generate automation "turn off lights when no motion for 10 minutes"
        hactl generate automation "notify when front door opens while away"
        hactl generate automation "morning routine on weekdays"
    """
    from hactl.handlers import ai_generator
    ai_generator.generate_automation(description)


@generate_group.command('blueprint')
@click.argument('description')
def generate_blueprint(description):
    """Generate blueprint YAML from description

    Generates a reusable blueprint that can be used for multiple
    automations with different entities.

    Examples:

    \b
        hactl generate blueprint "motion-activated lighting for any room"
        hactl generate blueprint "door open notification with customizable delay"
        hactl generate blueprint "temperature-based climate control"
    """
    from hactl.handlers import ai_generator
    ai_generator.generate_blueprint(description)


@generate_group.command('script')
@click.argument('description')
def generate_script(description):
    """Generate script YAML from description

    Generates a script that can be called from automations or manually.

    Examples:

    \b
        hactl generate script "bedtime routine - lights off and lock doors"
        hactl generate script "movie mode - dim lights and close blinds"
        hactl generate script "morning briefing announcement"
    """
    from hactl.handlers import ai_generator
    ai_generator.generate_script(description)


@generate_group.command('list')
@click.option('--category', '-c', type=click.Choice(['dashboards', 'automations', 'blueprints', 'scripts']),
              help='Filter by category')
def generate_list(category):
    """List all AI-generated content

    Shows all generated files with their status (applied or not).

    Examples:

    \b
        hactl generate list
        hactl generate list --category dashboards
        hactl generate list --category automations
    """
    from hactl.handlers import ai_generator
    ai_generator.list_generated(category)


@generate_group.command('apply')
@click.argument('file_path', type=click.Path(exists=True))
def generate_apply(file_path):
    """Apply generated content to Home Assistant

    Marks the generated file as applied and provides instructions
    for integrating it with Home Assistant.

    Examples:

    \b
        hactl generate apply generated/dashboards/2024-01-15_energy_monitoring.yaml
        hactl generate apply generated/automations/2024-01-15_motion_lights.yaml
    """
    from hactl.handlers import ai_generator
    ai_generator.apply_generated(file_path)
