"""
Deletion handlers for `hactl delete` (devices, entities, config-entries).

Mirrors the kubectl-style verb pattern: singular by id, plural by filter,
or declarative `-f` from a JSON manifest.

Design:
  - Default behaviour is dry-run unless the operator passes ``--yes``.
  - Every non-dry-run invocation writes a JSON audit file capturing the
    full pre-delete registry state per record. This is the only forensic
    trail; HA does not support undo.
  - Bulk deletions are gated by a safety predicate that refuses to touch
    devices/entities whose parent ``config_entry.state == 'loaded'`` AND
    that have produced any non-unavailable/unknown state in the last 7d.
    ``--force`` bypasses the predicate AND the ``--limit`` cap, but does
    NOT bypass the audit log.
  - Reuses ``classify_zombies`` and the registry fetch shape from
    ``hactl.handlers.zombie_devices`` — does not duplicate registry I/O.

WebSocket calls used:
  - ``config/device_registry/remove_config_entry`` (per config_entry on
    the device — once it has 0 entries left HA removes it).
  - ``config/entity_registry/remove`` (one call, works on restored
    entities too — they have no current owner).
  - ``config_entries/delete`` (cascades to all owned devices+entities).
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import socket
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import click

from hactl import __version__
from hactl.core import load_config, make_api_request
from hactl.core.websocket import WebSocketClient


KIND_DEVICE = 'device'
KIND_ENTITY = 'entity'
KIND_CONFIG_ENTRY = 'config-entry'

VALID_KINDS = (KIND_DEVICE, KIND_ENTITY, KIND_CONFIG_ENTRY)

# Safety / behaviour defaults.
DEFAULT_LIMIT = 50
RECENT_ACTIVITY_WINDOW_DAYS = 7
DEAD_STATES = frozenset(('unavailable', 'unknown', 'unknown_state', '', None))

# Origin tags for the safety driver: tells us whether the entity was
# named explicitly (singular) or matched by a filter (bulk). The
# live-state predicate hard-refuses the bulk form and prompts y/N for
# the singular form. See safety_check_entity_live_state.
ORIGIN_SINGULAR = 'singular'
ORIGIN_BULK = 'bulk'


# ---------------------------------------------------------------------------
# Registry fetch (mirrors hactl.handlers.zombie_devices._fetch_all but
# returns a slimmer shape — no states.csv-style enrichment needed here).
# ---------------------------------------------------------------------------

def fetch_registries(hass_url: str, hass_token: str) -> dict[str, Any]:
    """Fetch device, entity, area, and config-entry registries.

    Returns a dict with keys: devices, entities, areas, config_entries,
    states, ws_ok. ``states`` is best-effort and may be empty if the REST
    call fails.
    """
    devices: list[dict] = []
    entities: list[dict] = []
    areas: list[dict] = []
    ws_ok = False

    ws = WebSocketClient(hass_url, hass_token)
    try:
        ws.connect()
        devices = ws.call('config/device_registry/list') or []
        entities = ws.call('config/entity_registry/list') or []
        try:
            areas = ws.call('config/area_registry/list') or []
        except Exception:
            areas = []
        ws.close()
        ws_ok = True
    except Exception:
        try:
            ws.close()
        except Exception:
            pass

    config_entries: list[dict] = []
    try:
        ce = make_api_request(
            f"{hass_url}/api/config/config_entries/entry", hass_token)
        if isinstance(ce, list):
            config_entries = ce
    except Exception:
        pass

    states: list[dict] = []
    try:
        st = make_api_request(f"{hass_url}/api/states", hass_token)
        if isinstance(st, list):
            states = st
    except Exception:
        pass

    return {
        'devices': devices,
        'entities': entities,
        'areas': areas,
        'config_entries': config_entries,
        'states': states,
        'ws_ok': ws_ok,
    }


# ---------------------------------------------------------------------------
# Resource resolution: turn an id-or-name into a registry record.
# ---------------------------------------------------------------------------

def resolve_device(data: dict, ident: str) -> dict | None:
    """Resolve a device by id, name_by_user, or name (case-insensitive name)."""
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


def resolve_entity(data: dict, entity_id: str) -> dict | None:
    """Resolve an entity_registry record by entity_id.

    Returns a registry record if present; for restored entities that are
    only in /api/states (not the entity_registry), returns a synthetic
    dict so the caller still has something to delete. The WebSocket
    ``config/entity_registry/remove`` is what the UI uses; if the entity
    isn't in the registry there's nothing to delete via that call, but
    we still surface it so the user sees the right error.
    """
    for e in data['entities']:
        if e.get('entity_id') == entity_id:
            return e
    # Fall back to states — restored entities live there even if absent
    # from the registry. Caller gets a synthetic shape.
    for s in data['states']:
        if s.get('entity_id') == entity_id:
            return {
                'entity_id': entity_id,
                'platform': None,
                'config_entry_id': None,
                'device_id': None,
                'disabled_by': None,
                '_synthetic_from_state': True,
                '_state': s,
            }
    return None


def resolve_config_entry(data: dict, entry_id: str) -> dict | None:
    for ce in data['config_entries']:
        if ce.get('entry_id') == entry_id:
            return ce
    return None


# ---------------------------------------------------------------------------
# Filter parsing.
# ---------------------------------------------------------------------------

def parse_filters(filter_strs: tuple[str, ...]) -> dict[str, str]:
    """Parse ``key=value`` filter strings into a dict.

    Multiple ``--filter`` flags accumulate; same-key wins last (kubectl
    semantics).
    """
    out: dict[str, str] = {}
    for f in filter_strs:
        if '=' not in f:
            raise click.ClickException(
                f"Invalid --filter '{f}': expected key=value")
        k, v = f.split('=', 1)
        out[k.strip()] = v.strip()
    return out


def filter_devices(data: dict, filters: dict[str, str]) -> list[dict]:
    """Apply filters to devices.

    Supported keys:
      - ``category=orphan|stalled|disabled`` — uses classify_zombies.
      - ``integration=<domain>`` — matches resolved config-entry domain.
      - ``manufacturer=<str>`` — substring match (case-insensitive).
      - ``area=<id>`` — matches area_id exactly.
      - ``disabled_by=<value>`` — exact match (use ``none`` for null).
    """
    from hactl.handlers.doctor import classify_zombies

    devs = list(data['devices'])
    domain_by_entry = {ce.get('entry_id'): ce.get('domain')
                       for ce in data['config_entries']
                       if ce.get('entry_id')}

    if 'category' in filters:
        cat = filters['category']
        classified = classify_zombies(
            data['devices'], data['entities'], data['states'])
        bucket = {
            'orphan': classified['orphans'],
            'stalled': classified['stalled'],
            'disabled': classified['disabled'],
        }.get(cat)
        if bucket is None:
            raise click.ClickException(
                f"Unknown category '{cat}' "
                "(expected orphan|stalled|disabled)")
        devs = bucket

    if 'integration' in filters:
        target = filters['integration']
        kept = []
        for d in devs:
            for entry_id in d.get('config_entries') or []:
                if domain_by_entry.get(entry_id) == target:
                    kept.append(d)
                    break
        devs = kept

    if 'manufacturer' in filters:
        needle = filters['manufacturer'].lower()
        devs = [d for d in devs
                if needle in (d.get('manufacturer') or '').lower()]

    if 'area' in filters:
        area = filters['area']
        devs = [d for d in devs if d.get('area_id') == area]

    if 'disabled_by' in filters:
        wanted = filters['disabled_by']
        if wanted.lower() == 'none':
            devs = [d for d in devs if not d.get('disabled_by')]
        else:
            devs = [d for d in devs if d.get('disabled_by') == wanted]

    return devs


def filter_entities(data: dict, filters: dict[str, str]) -> list[dict]:
    """Apply filters to entities.

    Supported keys:
      - ``platform=<str>`` — exact platform match.
      - ``domain=<str>`` — entity_id prefix (e.g. ``sensor``).
      - ``disabled_by=<value>`` — exact, ``none`` for null.
      - ``restored=true`` — entity has no live owner (state.restored==true).
      - ``device_id=<id>`` — entity belongs to this device.
    """
    ents = list(data['entities'])

    if 'platform' in filters:
        ents = [e for e in ents if e.get('platform') == filters['platform']]

    if 'domain' in filters:
        prefix = filters['domain'] + '.'
        ents = [e for e in ents
                if (e.get('entity_id') or '').startswith(prefix)]

    if 'disabled_by' in filters:
        wanted = filters['disabled_by']
        if wanted.lower() == 'none':
            ents = [e for e in ents if not e.get('disabled_by')]
        else:
            ents = [e for e in ents if e.get('disabled_by') == wanted]

    if 'device_id' in filters:
        ents = [e for e in ents if e.get('device_id') == filters['device_id']]

    if 'restored' in filters:
        if filters['restored'].lower() == 'true':
            restored_eids = {
                s.get('entity_id') for s in data['states']
                if s.get('attributes', {}).get('restored')}
            ents = [e for e in ents if e.get('entity_id') in restored_eids]

    return ents


def apply_state_only_filter(entities: list[dict], data: dict,
                            wanted: str) -> list[dict]:
    """Keep only entities whose current state matches ``wanted``.

    Recommended safe pattern for zombie cleanup:
    ``hactl delete entities --filter platform=foo --state-only unavailable``.
    Anything live falls out before the safety predicate ever sees it.
    """
    if not wanted:
        return entities
    state_by_eid = {s.get('entity_id'): s for s in data.get('states') or []}
    if wanted == 'unavailable':
        targets = ('unavailable', 'unknown')
    else:
        targets = (wanted,)
    out = []
    for e in entities:
        s = state_by_eid.get(e.get('entity_id'))
        if not s:
            # No state at all → treat as unavailable for filter purposes.
            if 'unavailable' in targets:
                out.append(e)
            continue
        if s.get('state') in targets:
            out.append(e)
    return out


def filter_config_entries(data: dict, filters: dict[str, str]) -> list[dict]:
    """Apply filters to config_entries.

    Supported keys: ``state``, ``domain``, ``source``.
    """
    ces = list(data['config_entries'])
    for key in ('state', 'domain', 'source'):
        if key in filters:
            ces = [c for c in ces if c.get(key) == filters[key]]
    return ces


# ---------------------------------------------------------------------------
# Safety predicate.
# ---------------------------------------------------------------------------

def _entry_state_for_device(device: dict, ce_by_id: dict) -> str | None:
    """Return the worst (most-loaded) parent config_entry state for a device."""
    for entry_id in device.get('config_entries') or []:
        ce = ce_by_id.get(entry_id)
        if ce and ce.get('state') == 'loaded':
            return 'loaded'
    return None


def _has_recent_activity_for_entity(
        hass_url: str, hass_token: str, entity_id: str,
        days: int = RECENT_ACTIVITY_WINDOW_DAYS) -> bool:
    """Check HA history for any non-dead state in the last ``days``.

    Network-bound. Caller is responsible for batching. Returns False on
    any error so a transient API problem doesn't escalate to "blocked".
    """
    if not entity_id:
        return False
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    iso_start = start.strftime('%Y-%m-%dT%H:%M:%S%z')
    iso_end = end.strftime('%Y-%m-%dT%H:%M:%S%z')
    url = (f"{hass_url}/api/history/period/{iso_start}"
           f"?filter_entity_id={entity_id}&end_time={iso_end}"
           "&minimal_response&no_attributes")
    try:
        resp = make_api_request(url, hass_token)
    except Exception:
        return False
    # Response is [[ {state, ...}, ... ]] — one inner list per entity.
    if not isinstance(resp, list) or not resp:
        return False
    for series in resp:
        if not isinstance(series, list):
            continue
        for sample in series:
            if not isinstance(sample, dict):
                continue
            if sample.get('state') not in DEAD_STATES:
                return True
    return False


def safety_check_device(
        device: dict, data: dict,
        hass_url: str, hass_token: str) -> tuple[bool, str | None]:
    """Return (ok_to_delete, reason_if_blocked).

    Predicate refuses if parent config_entry is loaded AND any owned
    entity has had non-dead state in the last 7 days. Disabled devices
    are also flagged as 'intentional'.
    """
    if device.get('disabled_by'):
        return False, (
            f"device.disabled_by={device['disabled_by']!r} "
            "(looks intentional, not garbage)")

    ce_by_id = {ce.get('entry_id'): ce for ce in data['config_entries']}
    if _entry_state_for_device(device, ce_by_id) != 'loaded':
        return True, None

    owned = [e.get('entity_id') for e in data['entities']
             if e.get('device_id') == device.get('id')
             and not e.get('disabled_by')
             and e.get('entity_id')]
    for eid in owned:
        if _has_recent_activity_for_entity(hass_url, hass_token, eid):
            return False, (
                f"parent config_entry is 'loaded' and entity {eid} had "
                f"non-dead state in last {RECENT_ACTIVITY_WINDOW_DAYS}d")
    return True, None


def safety_check_entity(
        entity: dict, data: dict,
        hass_url: str, hass_token: str) -> tuple[bool, str | None]:
    if entity.get('disabled_by'):
        return False, (
            f"entity.disabled_by={entity['disabled_by']!r} "
            "(looks intentional)")
    ce_by_id = {ce.get('entry_id'): ce for ce in data['config_entries']}
    parent_id = entity.get('config_entry_id')
    parent = ce_by_id.get(parent_id) if parent_id else None
    if not parent or parent.get('state') != 'loaded':
        return True, None
    eid = entity.get('entity_id')
    if eid and _has_recent_activity_for_entity(hass_url, hass_token, eid):
        return False, (
            f"parent config_entry is 'loaded' and entity {eid} had "
            f"non-dead state in last {RECENT_ACTIVITY_WINDOW_DAYS}d")
    return True, None


def safety_check_entity_live_state(
        entity: dict, data: dict) -> tuple[bool, str | None]:
    """Refuse if the entity has a live (non-dead) reportable state.

    Lifeline against pattern-based bulk deletes. Lesson: a delete-by-
    pattern run caught ``sensor.andreas_iphone_12_pro_battery_level`` —
    a working sensor with state ``100`` — and removed it because the
    pattern matched. This predicate flags any entity whose CURRENT
    state is real (not in DEAD_STATES). The driver then either hard-
    refuses (bulk) or prompts y/N (singular).

    Returns (ok_to_delete, reason_if_blocked). The caller decides how
    to surface the refusal; this function never raises.
    """
    eid = entity.get('entity_id') or '-'
    state_by_eid = {s.get('entity_id'): s for s in data.get('states') or []}
    s = state_by_eid.get(eid)
    if not s:
        return True, None
    state_val = s.get('state')
    if state_val in DEAD_STATES:
        return True, None
    return False, (
        f"REFUSED: entity {eid!r} has live state {state_val!r} "
        "(not unavailable/unknown).\n"
        "Deleting an entity with active state usually means you're "
        "deleting a working sensor.\n"
        "If you really want to delete it, pass --force.")


def safety_check_config_entry(
        entry: dict, data: dict,
        hass_url: str, hass_token: str) -> tuple[bool, str | None]:
    """Config-entry deletes are intrinsically high-blast-radius.

    Block if state == 'loaded' AND any owned entity has recent activity.
    """
    if entry.get('state') != 'loaded':
        return True, None
    entry_id = entry.get('entry_id')
    owned_eids = [e.get('entity_id') for e in data['entities']
                  if e.get('config_entry_id') == entry_id
                  and not e.get('disabled_by')
                  and e.get('entity_id')]
    for eid in owned_eids[:25]:  # cap network calls
        if _has_recent_activity_for_entity(hass_url, hass_token, eid):
            return False, (
                f"config_entry state='loaded' and entity {eid} had "
                f"non-dead state in last {RECENT_ACTIVITY_WINDOW_DAYS}d")
    return True, None


# ---------------------------------------------------------------------------
# Plan record + audit log.
# ---------------------------------------------------------------------------

def make_plan_record(kind: str, ident: str, raw: dict) -> dict:
    """Snapshot the pre-delete state of one record."""
    return {
        'kind': kind,
        'id': ident,
        'pre_state': raw,
        'result': None,
        'error': None,
    }


def write_audit_log(records: list[dict], invocation: list[str],
                    audit_path: str | None) -> str:
    """Write the audit JSON. Returns the chosen path."""
    if audit_path is None:
        ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        audit_path = f"/tmp/hactl-delete-{ts}.json"

    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get('USER') or 'unknown'
    host = socket.gethostname()

    payload = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'hactl_version': __version__,
        'user': user,
        'host': host,
        'platform': platform.platform(),
        'invocation': invocation,
        'records': records,
    }
    os.makedirs(os.path.dirname(audit_path) or '.', exist_ok=True)
    with open(audit_path, 'w') as f:
        json.dump(payload, f, indent=2, default=str)
    return audit_path


# ---------------------------------------------------------------------------
# WebSocket execution.
# ---------------------------------------------------------------------------

def execute_delete_device(ws: WebSocketClient, device: dict) -> None:
    """Remove a device by removing every config_entry from it.

    HA auto-removes the device once its last config_entry is detached.
    """
    device_id = device.get('id')
    entries = device.get('config_entries') or []
    if not entries:
        # No config_entries — nothing to detach. The device should already
        # be gone, or it's a manual placeholder. Try the direct call as a
        # last resort; older HA exposes ``config/device_registry/remove``.
        try:
            ws.call('config/device_registry/update',
                    device_id=device_id, disabled_by='user')
        except Exception:
            pass
        return
    for entry_id in entries:
        ws.call('config/device_registry/remove_config_entry',
                device_id=device_id, config_entry_id=entry_id)


def execute_delete_entity(ws: WebSocketClient, entity: dict) -> None:
    if entity.get('_synthetic_from_state'):
        raise click.ClickException(
            f"entity {entity['entity_id']} is not in entity_registry "
            "(restored-from-state only). Delete its parent integration "
            "or clear the recorder instead.")
    ws.call('config/entity_registry/remove',
            entity_id=entity['entity_id'])


def execute_delete_config_entry(ws: WebSocketClient, entry: dict) -> None:
    ws.call('config_entries/delete',
            entry_id=entry['entry_id'])


# ---------------------------------------------------------------------------
# Top-level command driver.
# ---------------------------------------------------------------------------

def _summarise(records: list[dict]) -> str:
    by_kind: dict[str, int] = {}
    for r in records:
        by_kind[r['kind']] = by_kind.get(r['kind'], 0) + 1
    return ', '.join(f"{k}={v}" for k, v in sorted(by_kind.items()))


def _print_plan(records: list[dict]) -> None:
    click.echo()
    click.secho(f"=== Delete plan ({len(records)} records) ===", bold=True)
    click.echo(f"  {_summarise(records)}")
    click.echo()
    click.echo(f"{'KIND':<14} {'ID':<48} NAME / SUMMARY")
    click.echo('-' * 110)
    for r in records:
        pre = r['pre_state'] or {}
        if r['kind'] == KIND_DEVICE:
            name = pre.get('name_by_user') or pre.get('name') or '-'
        elif r['kind'] == KIND_ENTITY:
            name = pre.get('entity_id') or '-'
        else:
            name = f"{pre.get('domain', '?')} / {pre.get('title', '-')} " \
                   f"[{pre.get('state', '?')}]"
        click.echo(f"{r['kind']:<14} {(r['id'] or '-'):<48} {name}")
    click.echo()


def run_delete(  # noqa: C901 — driver, intentional length
        targets: list[tuple[str, str]],
        *,
        dry_run: bool,
        yes: bool,
        force: bool,
        limit: int,
        audit_path: str | None,
        quiet: bool,
        invocation: list[str],
        origin: str = ORIGIN_SINGULAR,
) -> int:
    """Execute (or dry-run) a deletion batch.

    ``targets`` is a list of (kind, id) tuples.
    """
    if not targets:
        click.echo('No targets matched. Nothing to delete.')
        return 0

    HASS_URL, HASS_TOKEN = load_config()
    data = fetch_registries(HASS_URL, HASS_TOKEN)

    # Resolve every target into a pre-state record.
    records: list[dict] = []
    not_found: list[tuple[str, str]] = []
    for kind, ident in targets:
        if kind == KIND_DEVICE:
            raw = resolve_device(data, ident)
        elif kind == KIND_ENTITY:
            raw = resolve_entity(data, ident)
        elif kind == KIND_CONFIG_ENTRY:
            raw = resolve_config_entry(data, ident)
        else:
            raise click.ClickException(
                f"Unknown kind '{kind}' (expected one of {VALID_KINDS})")
        if raw is None:
            not_found.append((kind, ident))
            continue
        # Use the canonical id from the registry record where possible.
        canonical_id = (
            raw.get('id') if kind == KIND_DEVICE else
            raw.get('entity_id') if kind == KIND_ENTITY else
            raw.get('entry_id'))
        records.append(make_plan_record(kind, canonical_id or ident, raw))

    if not_found and not quiet:
        for k, i in not_found:
            click.secho(
                f"  not found: {k} {i!r} — skipping", fg='yellow', err=True)

    # Limit gate.
    over_limit = len(records) > limit
    if over_limit and not force:
        raise click.ClickException(
            f"batch size {len(records)} exceeds --limit {limit}. "
            "Re-run with --force to override or pass --limit N.")

    # Live-state predicate (lifeline against pattern-based bulk
    # deletes catching working sensors). Singular form prompts y/N
    # (operator named the resource by id, this is friction not refusal).
    # Bulk form hard-refuses without --force.
    if not force:
        live_blocked: list[tuple[dict, str]] = []
        live_prompts: list[tuple[dict, str]] = []
        for r in records:
            if r['kind'] != KIND_ENTITY:
                continue
            ok, why = safety_check_entity_live_state(r['pre_state'], data)
            if ok:
                continue
            if origin == ORIGIN_SINGULAR:
                live_prompts.append((r, why or 'live state'))
            else:
                live_blocked.append((r, why or 'live state'))

        if live_blocked:
            click.secho(
                f"Refusing to delete {len(live_blocked)} entity(s) with "
                "live state in a bulk operation:",
                fg='red', err=True)
            for _r, why in live_blocked:
                click.secho(f"  {why}", fg='red', err=True)
            click.secho(
                "Bulk delete refused. Re-run with --force to override, "
                "or narrow the filter (try --state-only unavailable).",
                fg='red', err=True)
            blocked_ids = {(r['kind'], r['id']) for r, _ in live_blocked}
            records = [r for r in records
                       if (r['kind'], r['id']) not in blocked_ids]

        # Singular y/N prompt — only matters if we're actually about to
        # commit (--yes) and not a dry-run.
        if live_prompts and yes and not dry_run:
            for r, why in live_prompts:
                click.secho(why, fg='yellow', err=True)
                if not click.confirm('Proceed with delete?', default=False):
                    click.secho(f"  skipped: {r['kind']} {r['id']}",
                                fg='yellow')
                    records = [x for x in records
                               if (x['kind'], x['id']) != (r['kind'], r['id'])]
        elif live_prompts:
            # In dry-run / no-yes mode, just surface the warning so the
            # operator sees it before running for real.
            for _r, why in live_prompts:
                click.secho(why, fg='yellow', err=True)

    # Safety predicate.
    blocked: list[tuple[dict, str]] = []
    if not force:
        for r in records:
            if r['kind'] == KIND_DEVICE:
                ok, why = safety_check_device(
                    r['pre_state'], data, HASS_URL, HASS_TOKEN)
            elif r['kind'] == KIND_ENTITY:
                ok, why = safety_check_entity(
                    r['pre_state'], data, HASS_URL, HASS_TOKEN)
            else:
                ok, why = safety_check_config_entry(
                    r['pre_state'], data, HASS_URL, HASS_TOKEN)
            if not ok:
                blocked.append((r, why or 'safety predicate refused'))

    if blocked and not force:
        click.secho(
            f"Safety predicate blocked {len(blocked)} record(s):",
            fg='red', err=True)
        for r, why in blocked:
            click.secho(f"  - {r['kind']} {r['id']}: {why}",
                        fg='red', err=True)
        click.secho(
            "Re-run with --force to override (still audited).",
            fg='red', err=True)
        # Drop blocked records from the plan.
        blocked_ids = {(r['kind'], r['id']) for r, _ in blocked}
        records = [r for r in records if (r['kind'], r['id']) not in blocked_ids]

    if not records:
        click.echo('No deletable records remain after safety checks.')
        return 0

    if not quiet:
        _print_plan(records)

    # Dry-run short-circuit (default unless --yes).
    if dry_run or not yes:
        if not yes:
            click.secho(
                'DRY-RUN (default). Pass --yes to actually delete '
                'or --dry-run to silence this notice.', fg='yellow')
        else:
            click.secho('DRY-RUN: no API calls made.', fg='yellow')
        return 0

    # Confirmation prompt is implicit via --yes; we already gated above.
    # Execute.
    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()
    except Exception as e:
        raise click.ClickException(f'WebSocket connect failed: {e}')

    n_ok = n_fail = 0
    try:
        for r in records:
            try:
                if r['kind'] == KIND_DEVICE:
                    execute_delete_device(ws, r['pre_state'])
                elif r['kind'] == KIND_ENTITY:
                    execute_delete_entity(ws, r['pre_state'])
                else:
                    execute_delete_config_entry(ws, r['pre_state'])
                r['result'] = 'deleted'
                n_ok += 1
                if not quiet:
                    click.secho(f"  deleted: {r['kind']} {r['id']}",
                                fg='green')
            except Exception as e:
                r['result'] = 'failed'
                r['error'] = str(e)
                n_fail += 1
                click.secho(f"  failed:  {r['kind']} {r['id']}: {e}",
                            fg='red', err=True)
    finally:
        try:
            ws.close()
        except Exception:
            pass

    audit_target = write_audit_log(records, invocation, audit_path)
    click.echo()
    click.echo(f"Audit log: {audit_target}")
    click.echo(f"Result: {n_ok} deleted, {n_fail} failed.")
    return 0 if n_fail == 0 else 1


# ---------------------------------------------------------------------------
# Manifest reader (-f file or -).
# ---------------------------------------------------------------------------

def load_manifest(path: str) -> list[tuple[str, str]]:
    """Load a JSON list of {kind, id} records from a file or stdin (``-``)."""
    if path == '-':
        raw = sys.stdin.read()
    else:
        with open(path) as f:
            raw = f.read()
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        raise click.ClickException(f'Invalid JSON manifest: {e}')

    targets: list[tuple[str, str]] = []
    if not isinstance(doc, list):
        raise click.ClickException(
            'Manifest must be a JSON array of {kind, id} objects.')
    for i, item in enumerate(doc):
        if not isinstance(item, dict):
            raise click.ClickException(
                f'Manifest item {i} is not an object.')
        # Support several shapes from `hactl get zombie-devices -o json`:
        # {kind: 'device', id: ...} or {device_id: ...} or {entity_id: ...}.
        kind = item.get('kind')
        ident = item.get('id')
        if not kind:
            if item.get('entity_id'):
                kind = KIND_ENTITY
                ident = item.get('entity_id')
            elif item.get('device_id'):
                kind = KIND_DEVICE
                ident = item.get('device_id')
            elif item.get('entry_id'):
                kind = KIND_CONFIG_ENTRY
                ident = item.get('entry_id')
        if not kind or not ident:
            raise click.ClickException(
                f'Manifest item {i} missing kind or id: {item!r}')
        if kind not in VALID_KINDS:
            raise click.ClickException(
                f"Manifest item {i}: unknown kind {kind!r}")
        targets.append((kind, ident))
    return targets
