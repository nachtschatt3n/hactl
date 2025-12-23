"""
Memory command group for hactl
"""

import click


@click.group('memory')
def memory_group():
    """AI memory and context management"""
    pass


@memory_group.command('add')
@click.argument('category', type=click.Choice(['sensor', 'device', 'automation', 'dashboard']))
@click.argument('item_id')
@click.argument('note')
def memory_add(category, item_id, note):
    """Add contextual note about a sensor/device/automation/dashboard

    Examples:

    \b
        hactl memory add sensor bedroom_temperature "Reads 2°C high, needs calibration"
        hactl memory add device living_room_light "Bulb flickers when dimmed below 30%"
        hactl memory add automation morning_routine "Only runs on weekdays"
    """
    from hactl.handlers import memory_mgmt
    memory_mgmt.add_note(category, item_id, note)


@memory_group.command('show')
@click.argument('category', type=click.Choice(['sensor', 'device', 'automation', 'dashboard']))
@click.argument('item_id', required=False)
def memory_show(category, item_id):
    """Show memory notes for a category or specific item

    Examples:

    \b
        hactl memory show sensor
        hactl memory show sensor bedroom_temperature
        hactl memory show device living_room_light
    """
    from hactl.handlers import memory_mgmt
    memory_mgmt.show_notes(category, item_id)


@memory_group.command('edit')
@click.argument('file_path')
def memory_edit(file_path):
    """Edit memory files directly

    Opens the file in your $EDITOR (defaults to nano).

    Examples:

    \b
        hactl memory edit context/preferences.md
        hactl memory edit context/ai_instructions.md
        hactl memory edit sensors/notes.json
    """
    from hactl.handlers import memory_mgmt
    memory_mgmt.edit_file(file_path)


@memory_group.command('sync')
@click.option('--category', '-c', multiple=True,
              type=click.Choice(['devices', 'sensors', 'automations', 'dashboards']),
              help='Specific categories to sync (can be used multiple times)')
def memory_sync(category):
    """Sync current Home Assistant state to memory

    Fetches current devices, sensors, automations, and dashboards
    and stores them in the memory directory for AI context.

    Examples:

    \b
        hactl memory sync
        hactl memory sync --category sensors
        hactl memory sync --category devices --category sensors
    """
    from hactl.handlers import memory_mgmt
    categories = list(category) if category else None
    memory_mgmt.sync_from_hass(categories)


@memory_group.command('list')
def memory_list():
    """List all memory contents

    Shows what files are stored in the memory directory.

    Examples:

    \b
        hactl memory list
    """
    from hactl.handlers import memory_mgmt
    memory_mgmt.list_memory()
