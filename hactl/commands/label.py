"""
LABEL command group for hactl — kubectl-style.

Subcommands:

  - ``hactl label list``   — show every label in the registry plus
                              device/entity usage counts.
  - ``hactl label apply``  — add a label to one or more devices /
                              entities (or to every device matched by an
                              allowlist YAML via ``--from-allowlist``).
  - ``hactl label remove`` — remove a label from one or more devices /
                              entities.

Hard rules (mirror ``hactl delete``):
  - default is dry-run unless ``--yes``
  - audit log written when the run actually mutates HA
  - ``--limit`` defaults to 200 changing-records per batch (labelling
    is reversible, so the limit is looser than for delete)
"""

from __future__ import annotations

import sys

import click

from hactl.handlers import labels as labels_h


DEFAULT_LIMIT = 200


def _common_apply_opts(func):
    """Shared --dry-run/--yes/--limit/--audit/--quiet."""
    func = click.option('--quiet', is_flag=True, default=False,
                        help='Suppress per-record progress output.')(func)
    func = click.option('--audit', 'audit_path', default=None,
                        type=click.Path(dir_okay=False),
                        help='Write audit JSON to this path '
                             '(default /tmp/hactl-label-<ts>.json).')(func)
    func = click.option('--limit', type=int, default=DEFAULT_LIMIT,
                        show_default=True,
                        help='Max changing records per batch.')(func)
    func = click.option('--yes', is_flag=True, default=False,
                        help='Commit. Without this, runs as dry-run.')(func)
    func = click.option('--dry-run', is_flag=True, default=False,
                        help='Force dry-run (no API calls). Default-on '
                             'unless --yes is passed.')(func)
    return func


@click.group('label')
def label_group():
    """Manage Home Assistant labels on devices and entities.

    \b
    Examples:
        hactl label list
        hactl label apply --device "Soil sensor 3" --label haghs_ignore
        hactl label apply --entity sensor.foo --label haghs_ignore
        hactl label apply --from-allowlist noise.yaml --label haghs_ignore
        hactl label remove --device "Soil sensor 3" --label haghs_ignore

    Default behaviour for apply/remove is DRY-RUN. Pass --yes to commit.
    """


# ---------------------------------------------------------------------------
# `hactl label list`
# ---------------------------------------------------------------------------

@label_group.command('list')
@click.option('--format', '-o', 'format_type',
              type=click.Choice(['table', 'json']), default='table',
              show_default=True, help='Output format.')
def label_list(format_type):
    """List every label in the HA label_registry with usage counts.

    \b
        hactl label list
        hactl label list -o json
    """
    rc = labels_h.cmd_list(format_type=format_type)
    raise SystemExit(rc)


# ---------------------------------------------------------------------------
# `hactl label apply`
# ---------------------------------------------------------------------------

@label_group.command('apply')
@click.option('--device', 'device_idents', multiple=True,
              help='Device id or name (case-insensitive). '
                   'Repeatable.')
@click.option('--entity', 'entity_idents', multiple=True,
              help='Entity id (e.g. sensor.foo). Repeatable.')
@click.option('--from-allowlist', 'from_allowlist', default=None,
              type=click.Path(dir_okay=False, exists=True),
              help='YAML allowlist (cberg noise_allowlist.yaml format). '
                   'Reads flaky_zigbee_devices and flaky_iot_devices.')
@click.option('--label', 'label', required=True,
              help='Label id to apply (auto-created if missing).')
@_common_apply_opts
@click.pass_context
def label_apply(ctx, device_idents, entity_idents, from_allowlist,
                label, dry_run, yes, limit, audit_path, quiet):
    """Add a label to devices and/or entities.

    \b
        hactl label apply --device "Soil sensor 3" --label haghs_ignore
        hactl label apply --entity sensor.foo --label haghs_ignore --yes
        hactl label apply --from-allowlist noise_allowlist.yaml \\
                          --label haghs_ignore --dry-run
    """
    rc = labels_h.run_label(
        device_idents=list(device_idents),
        entity_idents=list(entity_idents),
        from_allowlist=from_allowlist,
        label=label,
        add=True,
        dry_run=dry_run, yes=yes, limit=limit,
        audit_path=audit_path, quiet=quiet, invocation=sys.argv,
    )
    ctx.exit(rc)


# ---------------------------------------------------------------------------
# `hactl label remove`
# ---------------------------------------------------------------------------

@label_group.command('remove')
@click.option('--device', 'device_idents', multiple=True,
              help='Device id or name (case-insensitive). Repeatable.')
@click.option('--entity', 'entity_idents', multiple=True,
              help='Entity id (e.g. sensor.foo). Repeatable.')
@click.option('--from-allowlist', 'from_allowlist', default=None,
              type=click.Path(dir_okay=False, exists=True),
              help='YAML allowlist — same parser as `apply`. Strips the '
                   'label from every matched device.')
@click.option('--label', 'label', required=True,
              help='Label id to remove.')
@_common_apply_opts
@click.pass_context
def label_remove(ctx, device_idents, entity_idents, from_allowlist,
                 label, dry_run, yes, limit, audit_path, quiet):
    """Remove a label from devices and/or entities.

    \b
        hactl label remove --device "Soil sensor 3" --label haghs_ignore
        hactl label remove --entity sensor.foo --label haghs_ignore --yes
    """
    rc = labels_h.run_label(
        device_idents=list(device_idents),
        entity_idents=list(entity_idents),
        from_allowlist=from_allowlist,
        label=label,
        add=False,
        dry_run=dry_run, yes=yes, limit=limit,
        audit_path=audit_path, quiet=quiet, invocation=sys.argv,
    )
    ctx.exit(rc)
