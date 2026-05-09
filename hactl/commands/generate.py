"""
Generate command group for hactl - AI-assisted content generation
"""

import click


@click.group('generate')
def generate_group():
    """AI-assisted generation of dashboards, automations, blueprints, and scripts"""
    pass


@generate_group.command('dashboard')
@click.argument('description')
def generate_dashboard(description):
    """Generate a dashboard YAML template

    \b
    Examples:
        hactl generate dashboard "energy monitoring"
        hactl generate dashboard "bedroom controls"
    """
    from hactl.handlers import ai_generator
    ai_generator.generate_content('dashboard', description)


@generate_group.command('automation')
@click.argument('description')
def generate_automation(description):
    """Generate an automation YAML template

    \b
    Examples:
        hactl generate automation "turn off lights after 10 minutes"
        hactl generate automation "morning routine"
    """
    from hactl.handlers import ai_generator
    ai_generator.generate_content('automation', description)


@generate_group.command('blueprint')
@click.argument('description')
def generate_blueprint(description):
    """Generate a blueprint YAML template

    \b
    Examples:
        hactl generate blueprint "motion activated lights"
    """
    from hactl.handlers import ai_generator
    ai_generator.generate_content('blueprint', description)


@generate_group.command('script')
@click.argument('description')
def generate_script(description):
    """Generate a script YAML template

    \b
    Examples:
        hactl generate script "bedtime routine"
    """
    from hactl.handlers import ai_generator
    ai_generator.generate_content('script', description)


@generate_group.command('list')
@click.option('--category', '-c',
              type=click.Choice(['dashboards', 'automations', 'blueprints', 'scripts']),
              default=None,
              help='Filter by category')
def generate_list(category):
    """List all generated content

    \b
    Examples:
        hactl generate list
        hactl generate list --category dashboards
    """
    from hactl.handlers import ai_generator
    ai_generator.list_generated(category)


@generate_group.command('apply')
@click.argument('file_path')
def generate_apply(file_path):
    """Mark a generated file as applied and show apply instructions

    \b
    Examples:
        hactl generate apply generated/dashboards/energy_monitoring.yaml
    """
    from hactl.handlers import ai_generator
    ai_generator.apply_generated(file_path)
