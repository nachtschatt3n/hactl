"""
DELETE command group for hactl — kubectl-style.

Three deletable resource kinds (PR scope):

  - device       — ``config/device_registry/remove_config_entry`` per entry
  - entity       — ``config/entity_registry/remove``
  - config-entry — ``config_entries/delete`` (cascades)

Each kind has a singular form (id) and a plural form (filter-driven).
Bulk input via ``-f manifest.json`` (or ``-f -`` for stdin) is also
supported and is the canonical path for the
``hactl get zombie-devices -o json | hactl delete -f -`` workflow.

Hard rules:
  - default is dry-run unless ``--yes``
  - audit log always written when something gets deleted (``--force``
    cannot bypass)
  - ``--limit`` defaults to 50; ``--force`` bypasses both the limit and
    the safety predicate
"""

from __future__ import annotations

import sys

import click

from hactl.handlers import deletions


def _common_opts(func):
    """Apply the shared --dry-run/--yes/--limit/--force/--audit/--quiet."""
    func = click.option('--quiet', is_flag=True, default=False,
                        help='Suppress per-record progress output.')(func)
    func = click.option('--audit', 'audit_path', default=None,
                        type=click.Path(dir_okay=False),
                        help='Write audit JSON to this path '
                             '(default /tmp/hactl-delete-<ts>.json).')(func)
    func = click.option('--force', is_flag=True, default=False,
                        help='Bypass the --limit cap AND the safety '
                             'predicate. Audit log is still written.')(func)
    func = click.option('--limit', type=int, default=deletions.DEFAULT_LIMIT,
                        show_default=True,
                        help='Max records per batch.')(func)
    func = click.option('--yes', is_flag=True, default=False,
                        help='Commit. Without this, runs as dry-run.')(func)
    func = click.option('--dry-run', is_flag=True, default=False,
                        help='Force dry-run (no API calls). Default-on '
                             'unless --yes is passed.')(func)
    return func


@click.group('delete', invoke_without_command=True)
@click.option('-f', '--from-file', 'from_file', default=None,
              type=click.Path(dir_okay=False),
              help='Read deletion manifest from JSON file (or "-" stdin).')
@_common_opts
@click.pass_context
def delete_group(ctx, from_file, dry_run, yes, limit, force,
                 audit_path, quiet):
    """Delete Home Assistant resources (kubectl-style).

    \b
    Singular by id:
        hactl delete device <id-or-name>
        hactl delete entity <entity_id>
        hactl delete config-entry <entry_id>

    \b
    Bulk by filter:
        hactl delete devices --filter category=orphan
        hactl delete entities --filter platform=tibber_prices
        hactl delete config-entries --filter state=not_loaded

    \b
    Bulk from manifest:
        hactl delete -f deletions.json
        hactl get zombie-devices -o json | hactl delete -f -

    Default behaviour is DRY-RUN. Pass --yes to actually delete.
    """
    if ctx.invoked_subcommand is not None:
        # Stash flags for subcommands to read.
        ctx.ensure_object(dict)
        ctx.obj.update({
            'dry_run': dry_run,
            'yes': yes,
            'limit': limit,
            'force': force,
            'audit_path': audit_path,
            'quiet': quiet,
        })
        return

    # No subcommand → require -f (or fail with a clear hint).
    if not from_file:
        click.echo(ctx.get_help())
        ctx.exit(2)

    targets = deletions.load_manifest(from_file)
    rc = deletions.run_delete(
        targets,
        dry_run=dry_run,
        yes=yes,
        force=force,
        limit=limit,
        audit_path=audit_path,
        quiet=quiet,
        invocation=sys.argv,
    )
    ctx.exit(rc)


# ---------------------------------------------------------------------------
# Singular forms.
# ---------------------------------------------------------------------------

@delete_group.command('device')
@click.argument('ident')
@_common_opts
@click.pass_context
def delete_device(ctx, ident, dry_run, yes, limit, force, audit_path, quiet):
    """Delete a single device by id or name.

    \b
        hactl delete device 1a2b3c... --yes
        hactl delete device "Living Room Lamp" --dry-run
    """
    rc = deletions.run_delete(
        [(deletions.KIND_DEVICE, ident)],
        dry_run=dry_run, yes=yes, force=force, limit=limit,
        audit_path=audit_path, quiet=quiet, invocation=sys.argv,
    )
    ctx.exit(rc)


@delete_group.command('entity')
@click.argument('entity_id')
@_common_opts
@click.pass_context
def delete_entity(ctx, entity_id, dry_run, yes, limit, force,
                  audit_path, quiet):
    """Delete a single entity by entity_id.

    \b
        hactl delete entity sensor.foo --yes
        hactl delete entity sensor.foo --dry-run
    """
    rc = deletions.run_delete(
        [(deletions.KIND_ENTITY, entity_id)],
        dry_run=dry_run, yes=yes, force=force, limit=limit,
        audit_path=audit_path, quiet=quiet, invocation=sys.argv,
    )
    ctx.exit(rc)


@delete_group.command('config-entry')
@click.argument('entry_id')
@_common_opts
@click.pass_context
def delete_config_entry(ctx, entry_id, dry_run, yes, limit, force,
                        audit_path, quiet):
    """Delete a single config_entry. Cascades to all devices+entities.

    \b
        hactl delete config-entry abc123 --dry-run
        hactl delete config-entry abc123 --yes
    """
    rc = deletions.run_delete(
        [(deletions.KIND_CONFIG_ENTRY, entry_id)],
        dry_run=dry_run, yes=yes, force=force, limit=limit,
        audit_path=audit_path, quiet=quiet, invocation=sys.argv,
    )
    ctx.exit(rc)


# ---------------------------------------------------------------------------
# Plural / filter forms.
# ---------------------------------------------------------------------------

@delete_group.command('devices')
@click.option('--filter', 'filter_strs', multiple=True,
              help='key=value filter (repeatable). '
                   'Keys: category, integration, manufacturer, area, '
                   'disabled_by.')
@_common_opts
@click.pass_context
def delete_devices(ctx, filter_strs, dry_run, yes, limit, force,
                   audit_path, quiet):
    """Bulk-delete devices matching --filter expressions.

    \b
        hactl delete devices --filter category=orphan --dry-run
        hactl delete devices --filter integration=bluetooth --yes
    """
    from hactl.core import load_config
    HASS_URL, HASS_TOKEN = load_config()
    data = deletions.fetch_registries(HASS_URL, HASS_TOKEN)
    filters = deletions.parse_filters(filter_strs)
    matched = deletions.filter_devices(data, filters)
    targets = [(deletions.KIND_DEVICE, d.get('id')) for d in matched
               if d.get('id')]
    rc = deletions.run_delete(
        targets, dry_run=dry_run, yes=yes, force=force, limit=limit,
        audit_path=audit_path, quiet=quiet, invocation=sys.argv,
    )
    ctx.exit(rc)


@delete_group.command('entities')
@click.option('--filter', 'filter_strs', multiple=True,
              help='key=value filter (repeatable). '
                   'Keys: platform, domain, disabled_by, device_id, '
                   'restored.')
@_common_opts
@click.pass_context
def delete_entities(ctx, filter_strs, dry_run, yes, limit, force,
                    audit_path, quiet):
    """Bulk-delete entities matching --filter expressions.

    \b
        hactl delete entities --filter platform=tibber_prices --dry-run
        hactl delete entities --filter domain=sensor --filter restored=true
    """
    from hactl.core import load_config
    HASS_URL, HASS_TOKEN = load_config()
    data = deletions.fetch_registries(HASS_URL, HASS_TOKEN)
    filters = deletions.parse_filters(filter_strs)
    matched = deletions.filter_entities(data, filters)
    targets = [(deletions.KIND_ENTITY, e.get('entity_id'))
               for e in matched if e.get('entity_id')]
    rc = deletions.run_delete(
        targets, dry_run=dry_run, yes=yes, force=force, limit=limit,
        audit_path=audit_path, quiet=quiet, invocation=sys.argv,
    )
    ctx.exit(rc)


@delete_group.command('config-entries')
@click.option('--filter', 'filter_strs', multiple=True,
              help='key=value filter (repeatable). '
                   'Keys: state, domain, source.')
@_common_opts
@click.pass_context
def delete_config_entries(ctx, filter_strs, dry_run, yes, limit, force,
                          audit_path, quiet):
    """Bulk-delete config_entries matching --filter.

    \b
        hactl delete config-entries --filter state=not_loaded --dry-run
        hactl delete config-entries --filter domain=unifi --yes
    """
    from hactl.core import load_config
    HASS_URL, HASS_TOKEN = load_config()
    data = deletions.fetch_registries(HASS_URL, HASS_TOKEN)
    filters = deletions.parse_filters(filter_strs)
    matched = deletions.filter_config_entries(data, filters)
    targets = [(deletions.KIND_CONFIG_ENTRY, c.get('entry_id'))
               for c in matched if c.get('entry_id')]
    rc = deletions.run_delete(
        targets, dry_run=dry_run, yes=yes, force=force, limit=limit,
        audit_path=audit_path, quiet=quiet, invocation=sys.argv,
    )
    ctx.exit(rc)
