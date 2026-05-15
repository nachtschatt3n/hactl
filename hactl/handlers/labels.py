"""
Label handlers for `hactl label`.

Generic kubectl-style verb for managing Home Assistant **label_registry**
labels on devices and entities. Plus an ``--from-allowlist`` mode that
reads a YAML allowlist (e.g. cberg's ``noise_allowlist.yaml``) and
auto-applies a target label to every matched device.

WebSocket calls used:
  - ``config/label_registry/list``        (read)
  - ``config/label_registry/create``      (idempotent ensure)
  - ``config/device_registry/list``       (resolve devices)
  - ``config/device_registry/update``     (REPLACES labels list)
  - ``config/entity_registry/list``       (resolve entities)
  - ``config/entity_registry/update``     (REPLACES labels list)

Important HA semantics: ``*_registry/update`` REPLACES the ``labels``
list — it does NOT merge. Every code path in this module reads the
current labels first, computes the new set, and only writes when the
set actually changes. That is how idempotency is enforced.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import socket
from datetime import datetime, timezone
from typing import Any, Iterable

import click

from hactl import __version__
from hactl.core import load_config
from hactl.core.websocket import WebSocketClient


# Default audit dir.
AUDIT_DIR_DEFAULT = '/tmp'

# Allowlist sections we look at. Order matters only for output.
ALLOWLIST_SECTIONS = ('flaky_zigbee_devices', 'flaky_iot_devices')


# ---------------------------------------------------------------------------
# Registry fetch.
# ---------------------------------------------------------------------------

def fetch_registries(hass_url: str, hass_token: str) -> dict[str, Any]:
    """Pull device + entity + label registries.

    Returns ``{devices, entities, labels, ws_ok}``. On WS failure the
    lists are empty and ``ws_ok`` is False — callers should error out.
    """
    devices: list[dict] = []
    entities: list[dict] = []
    labels: list[dict] = []
    ws_ok = False

    ws = WebSocketClient(hass_url, hass_token)
    try:
        ws.connect()
        devices = ws.call('config/device_registry/list') or []
        entities = ws.call('config/entity_registry/list') or []
        try:
            labels = ws.call('config/label_registry/list') or []
        except Exception:
            # Older HA may not expose label_registry — treat as empty.
            labels = []
        ws.close()
        ws_ok = True
    except Exception:
        try:
            ws.close()
        except Exception:
            pass

    return {
        'devices': devices,
        'entities': entities,
        'labels': labels,
        'ws_ok': ws_ok,
    }


# ---------------------------------------------------------------------------
# Resource resolution.
# ---------------------------------------------------------------------------

def resolve_device(data: dict, ident: str) -> dict | None:
    """Resolve a device by id, then by name_by_user / name (case-insensitive)."""
    if not ident:
        return None
    for d in data['devices']:
        if d.get('id') == ident:
            return d
    lower = ident.lower()
    for d in data['devices']:
        if (d.get('name_by_user') or '').lower() == lower:
            return d
        if (d.get('name') or '').lower() == lower:
            return d
    return None


def resolve_device_fuzzy(data: dict, ident: str) -> dict | None:
    """Case-insensitive substring match on name_by_user/name. Used as a
    last-resort fallback by --from-allowlist when an exact match fails.
    Returns the FIRST match (deterministic on registry order)."""
    if not ident:
        return None
    needle = ident.lower()
    for d in data['devices']:
        haystacks = (d.get('name_by_user') or '', d.get('name') or '')
        for h in haystacks:
            if h and needle in h.lower():
                return d
    return None


def resolve_entity(data: dict, entity_id: str) -> dict | None:
    if not entity_id:
        return None
    for e in data['entities']:
        if e.get('entity_id') == entity_id:
            return e
    return None


# ---------------------------------------------------------------------------
# Allowlist parser.
# ---------------------------------------------------------------------------

def parse_allowlist(path: str) -> list[str]:
    """Extract device-name strings from an allowlist YAML.

    Walks the ``flaky_zigbee_devices`` and ``flaky_iot_devices`` lists.
    Each item may be a bare string, or an object with a ``name`` key.
    Returns names in source order, dedup'd while preserving order.

    Other allowlist sections (alerts, services, etc.) are ignored — this
    is strictly a device-name extractor.
    """
    import yaml  # local import — keeps base import path light
    with open(path) as f:
        try:
            doc = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise click.ClickException(f'Invalid YAML in {path}: {e}')
    if not isinstance(doc, dict):
        raise click.ClickException(
            f'Allowlist {path}: top-level must be a mapping')

    names: list[str] = []
    seen: set[str] = set()
    for section in ALLOWLIST_SECTIONS:
        items = doc.get(section) or []
        if not isinstance(items, list):
            continue
        for item in items:
            name: str | None = None
            if isinstance(item, str):
                name = item.strip()
            elif isinstance(item, dict):
                raw = item.get('name')
                if isinstance(raw, str):
                    name = raw.strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Label registry helpers.
# ---------------------------------------------------------------------------

def label_exists(data: dict, label_id: str) -> bool:
    if not label_id:
        return False
    for lab in data.get('labels') or []:
        if lab.get('label_id') == label_id or lab.get('name') == label_id:
            return True
    return False


def ensure_label(ws: WebSocketClient, data: dict, label_id: str,
                 *, dry_run: bool) -> tuple[bool, str | None]:
    """Ensure the target label exists in the label_registry.

    Returns ``(was_created, error_or_none)``. If it already exists this
    is a no-op (returns False, None). If dry_run is True we never call
    create — we just report what *would* happen via the bool.
    """
    if label_exists(data, label_id):
        return False, None
    if dry_run:
        # Patch the in-memory cache so subsequent records don't keep
        # claiming the label needs creating.
        data.setdefault('labels', []).append(
            {'label_id': label_id, 'name': label_id})
        return True, None
    try:
        ws.call('config/label_registry/create',
                name=label_id, label_id=label_id)
        # Refresh local cache so subsequent calls in the same run
        # don't try to recreate.
        data.setdefault('labels', []).append(
            {'label_id': label_id, 'name': label_id})
        return True, None
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Plan + diff.
# ---------------------------------------------------------------------------

def _planned_labels(current: Iterable[str] | None, label: str,
                    add: bool) -> tuple[list[str], list[str]]:
    """Compute (current_sorted, new_sorted) given an add/remove op.

    Always returns deterministic sorted lists so audit-log diffs are
    stable regardless of HA's input ordering.
    """
    cur = list(current or [])
    cur_sorted = sorted(set(cur))
    if add:
        new = sorted(set(cur) | {label})
    else:
        new = sorted(set(cur) - {label})
    return cur_sorted, new


def make_plan_record(kind: str, ident: str, raw: dict,
                     label: str, add: bool) -> dict:
    cur, new = _planned_labels(raw.get('labels'), label, add)
    return {
        'kind': kind,                       # 'device' or 'entity'
        'id': ident,
        'op': 'add' if add else 'remove',
        'label': label,
        'pre_labels': cur,
        'post_labels': new,
        'changed': cur != new,
        'result': None,
        'error': None,
        'pre_state': {
            'name': raw.get('name_by_user') or raw.get('name')
            if kind == 'device' else raw.get('entity_id'),
            'id': raw.get('id') if kind == 'device' else raw.get('entity_id'),
        },
    }


# ---------------------------------------------------------------------------
# Audit log.
# ---------------------------------------------------------------------------

def write_audit_log(records: list[dict],
                    label_creations: list[dict],
                    invocation: list[str],
                    audit_path: str | None) -> str:
    if audit_path is None:
        ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        audit_path = f'{AUDIT_DIR_DEFAULT}/hactl-label-{ts}.json'

    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get('USER') or 'unknown'

    payload = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'hactl_version': __version__,
        'user': user,
        'host': socket.gethostname(),
        'platform': platform.platform(),
        'invocation': invocation,
        'label_creations': label_creations,
        'records': records,
    }
    os.makedirs(os.path.dirname(audit_path) or '.', exist_ok=True)
    with open(audit_path, 'w') as f:
        json.dump(payload, f, indent=2, default=str)
    return audit_path


# ---------------------------------------------------------------------------
# WebSocket execution.
# ---------------------------------------------------------------------------

def execute_label_device(ws: WebSocketClient, device_id: str,
                         new_labels: list[str]) -> None:
    ws.call('config/device_registry/update',
            device_id=device_id, labels=new_labels)


def execute_label_entity(ws: WebSocketClient, entity_id: str,
                         new_labels: list[str]) -> None:
    ws.call('config/entity_registry/update',
            entity_id=entity_id, labels=new_labels)


# ---------------------------------------------------------------------------
# Plan printer.
# ---------------------------------------------------------------------------

def _print_label_plan(records: list[dict],
                      label_creations: list[dict],
                      unmatched: list[str],
                      *, label: str, op: str) -> None:
    click.echo()
    click.secho(f'=== Label plan ({op} {label}) ===', bold=True)
    n_change = sum(1 for r in records if r['changed'])
    n_noop = len(records) - n_change
    click.echo(f'  records:       {len(records)} '
               f'({n_change} changed, {n_noop} no-op)')
    if label_creations:
        click.echo(f'  label_create:  {len(label_creations)} '
                   f'({", ".join(c["label_id"] for c in label_creations)})')
    if unmatched:
        click.echo(f'  unmatched:     {len(unmatched)}')
    click.echo()
    if records:
        click.echo(f'{"OP":<7} {"KIND":<7} {"ID/NAME":<48} '
                   f'PRE → POST')
        click.echo('-' * 110)
        for r in records:
            mark = 'change' if r['changed'] else 'no-op'
            name = (r.get('pre_state') or {}).get('name') or r['id']
            click.echo(
                f'{mark:<7} {r["kind"]:<7} {(name or "-")[:48]:<48} '
                f'{r["pre_labels"]} -> {r["post_labels"]}')
    if unmatched:
        click.echo()
        click.secho('Unmatched allowlist entries:', fg='yellow')
        for n in unmatched:
            click.secho(f'  - {n!r}', fg='yellow')
    click.echo()


# ---------------------------------------------------------------------------
# `hactl label list`.
# ---------------------------------------------------------------------------

def cmd_list(format_type: str = 'table') -> int:
    """List all labels in the registry, with usage counts."""
    HASS_URL, HASS_TOKEN = load_config()
    data = fetch_registries(HASS_URL, HASS_TOKEN)
    if not data['ws_ok']:
        raise click.ClickException(
            'WebSocket fetch failed — cannot list labels.')

    counts_dev: dict[str, int] = {}
    counts_ent: dict[str, int] = {}
    for d in data['devices']:
        for lab in d.get('labels') or []:
            counts_dev[lab] = counts_dev.get(lab, 0) + 1
    for e in data['entities']:
        for lab in e.get('labels') or []:
            counts_ent[lab] = counts_ent.get(lab, 0) + 1

    rows = []
    for lab in data['labels']:
        lid = lab.get('label_id') or lab.get('name') or ''
        rows.append({
            'label_id': lid,
            'name': lab.get('name') or lid,
            'description': lab.get('description') or '',
            'color': lab.get('color') or '',
            'devices': counts_dev.get(lid, 0),
            'entities': counts_ent.get(lid, 0),
        })
    # Surface labels that are in use but missing from the registry.
    known = {r['label_id'] for r in rows}
    for lid in sorted(set(counts_dev) | set(counts_ent)):
        if lid not in known:
            rows.append({
                'label_id': lid, 'name': lid, 'description': '(unregistered)',
                'color': '', 'devices': counts_dev.get(lid, 0),
                'entities': counts_ent.get(lid, 0),
            })
    rows.sort(key=lambda r: r['label_id'])

    if format_type == 'json':
        click.echo(json.dumps(rows, indent=2))
        return 0

    click.secho(f'=== Labels ({len(rows)}) ===', bold=True)
    if not rows:
        click.echo('  (none)')
        return 0
    click.echo(f'{"LABEL_ID":<24} {"DEVICES":>8} {"ENTITIES":>9}  NAME')
    click.echo('-' * 70)
    for r in rows:
        click.echo(f'{r["label_id"]:<24} {r["devices"]:>8} {r["entities"]:>9}'
                   f'  {r["name"]}')
    return 0


# ---------------------------------------------------------------------------
# `hactl label apply` / `hactl label remove` — driver.
# ---------------------------------------------------------------------------

def run_label(  # noqa: C901 — driver, intentional length
        *,
        device_idents: list[str],
        entity_idents: list[str],
        from_allowlist: str | None,
        label: str,
        add: bool,
        dry_run: bool,
        yes: bool,
        limit: int,
        audit_path: str | None,
        quiet: bool,
        invocation: list[str],
) -> int:
    """Execute (or dry-run) a label add/remove batch.

    One of ``device_idents``, ``entity_idents``, or ``from_allowlist``
    must be non-empty. Multiple sources accumulate; per-record dedup
    happens after resolution (by canonical id).
    """
    if not label:
        raise click.ClickException('--label is required')
    if not (device_idents or entity_idents or from_allowlist):
        raise click.ClickException(
            'No targets: pass --device, --entity, or --from-allowlist')

    HASS_URL, HASS_TOKEN = load_config()
    data = fetch_registries(HASS_URL, HASS_TOKEN)
    if not data['ws_ok']:
        raise click.ClickException(
            'WebSocket fetch failed — cannot read registries.')

    unmatched: list[str] = []
    fuzzy_warnings: list[tuple[str, str]] = []  # (allowlist_name, matched_name)

    # ------------------------------------------------------------------
    # Resolve device identities (explicit + allowlist).
    # ------------------------------------------------------------------
    resolved_devices: list[dict] = []
    seen_dev: set[str] = set()

    def _add_dev(d: dict | None, source_name: str | None = None) -> None:
        if not d:
            if source_name:
                unmatched.append(source_name)
            return
        did = d.get('id')
        if not did or did in seen_dev:
            return
        seen_dev.add(did)
        resolved_devices.append(d)

    for ident in device_idents:
        d = resolve_device(data, ident)
        if d is None:
            unmatched.append(ident)
        else:
            _add_dev(d)

    if from_allowlist:
        names = parse_allowlist(from_allowlist)
        for name in names:
            d = resolve_device(data, name)
            if d is None:
                d = resolve_device_fuzzy(data, name)
                if d is not None:
                    fuzzy_warnings.append((name, d.get('name_by_user')
                                           or d.get('name') or '?'))
            _add_dev(d, source_name=name)

    # ------------------------------------------------------------------
    # Resolve entity identities (explicit only — allowlist is device-only).
    # ------------------------------------------------------------------
    resolved_entities: list[dict] = []
    seen_ent: set[str] = set()
    for ident in entity_idents:
        e = resolve_entity(data, ident)
        if e is None:
            unmatched.append(ident)
            continue
        eid = e.get('entity_id')
        if not eid or eid in seen_ent:
            continue
        seen_ent.add(eid)
        resolved_entities.append(e)

    # ------------------------------------------------------------------
    # Build plan records.
    # ------------------------------------------------------------------
    records: list[dict] = []
    for d in resolved_devices:
        records.append(make_plan_record('device', d.get('id') or '',
                                        d, label, add=add))
    for e in resolved_entities:
        records.append(make_plan_record('entity', e.get('entity_id') or '',
                                        e, label, add=add))

    # Limit gate.
    changed_count = sum(1 for r in records if r['changed'])
    if changed_count > limit:
        raise click.ClickException(
            f'plan would change {changed_count} records, exceeds --limit '
            f'{limit}. Re-run with --limit N or narrow the input.')

    # ------------------------------------------------------------------
    # Determine whether the target label needs creating.
    # ------------------------------------------------------------------
    label_creations: list[dict] = []
    needs_create = add and not label_exists(data, label)

    if not quiet:
        if fuzzy_warnings:
            click.secho('Fuzzy matches (substring fallback):',
                        fg='yellow')
            for src, matched in fuzzy_warnings:
                click.secho(f'  {src!r} -> device {matched!r}',
                            fg='yellow')
        _print_label_plan(records, label_creations=(
            [{'label_id': label, 'op': 'create'}] if needs_create else []),
                          unmatched=unmatched, label=label,
                          op='add' if add else 'remove')

    # ------------------------------------------------------------------
    # Dry-run short-circuit.
    # ------------------------------------------------------------------
    if dry_run or not yes:
        if not yes:
            click.secho(
                'DRY-RUN (default). Pass --yes to actually apply '
                'or --dry-run to silence this notice.', fg='yellow')
        else:
            click.secho('DRY-RUN: no API calls made.', fg='yellow')
        return 0

    # ------------------------------------------------------------------
    # Idempotency short-circuit: if no record changes AND no label
    # needs creating, don't even open a WebSocket.
    # ------------------------------------------------------------------
    if changed_count == 0 and not needs_create:
        click.secho('No changes required (idempotent).', fg='green')
        return 0

    # ------------------------------------------------------------------
    # Execute.
    # ------------------------------------------------------------------
    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()
    except Exception as e:
        raise click.ClickException(f'WebSocket connect failed: {e}')

    n_ok = n_fail = 0
    try:
        # Ensure label exists (idempotent on the registry).
        if needs_create:
            created, err = ensure_label(ws, data, label, dry_run=False)
            if err:
                raise click.ClickException(
                    f'Could not create label {label!r}: {err}')
            if created:
                label_creations.append(
                    {'label_id': label, 'op': 'created'})
                if not quiet:
                    click.secho(f'  label created: {label}', fg='green')

        for r in records:
            if not r['changed']:
                r['result'] = 'noop'
                continue
            try:
                if r['kind'] == 'device':
                    execute_label_device(ws, r['id'], r['post_labels'])
                else:
                    execute_label_entity(ws, r['id'], r['post_labels'])
                r['result'] = 'updated'
                n_ok += 1
                if not quiet:
                    click.secho(
                        f'  {"+" if add else "-"}label {label} on '
                        f'{r["kind"]} {r["id"]}', fg='green')
            except Exception as e:
                r['result'] = 'failed'
                r['error'] = str(e)
                n_fail += 1
                click.secho(
                    f'  failed: {r["kind"]} {r["id"]}: {e}',
                    fg='red', err=True)
    finally:
        try:
            ws.close()
        except Exception:
            pass

    audit_target = write_audit_log(records, label_creations,
                                   invocation, audit_path)
    click.echo()
    click.echo(f'Audit log: {audit_target}')
    click.echo(
        f'Result: {n_ok} updated, {n_fail} failed, '
        f'{len(records) - n_ok - n_fail} no-op.')
    return 0 if n_fail == 0 else 1
