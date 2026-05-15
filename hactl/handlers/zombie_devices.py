"""
Zombie-devices triage handler for `hactl get zombie-devices`.

Provides triage-grade per-record output (table / JSON / CSV) that is much
richer than the doctor-summary view in `hactl doctor --check zombie_devices`.

Reuses the pure classification function `classify_zombies` from
`hactl.handlers.doctor` and enriches each record with:

  - full device_id (no truncation)
  - human-readable area name (resolved from the area registry)
  - real integration domain (resolved from config_entries, NOT manufacturer)
  - manufacturer / model / sw_version / hw_version / via_device_id
  - disabled_by, entity counts, last_seen
  - for restored entities: entity_id, real platform, friendly_name

Read-only. Removing devices is a manual UI action.
"""

import csv
import io
import json
import os
import sys
from datetime import datetime, timezone

import click

from hactl.core import load_config, make_api_request
from hactl.core.websocket import WebSocketClient
from hactl.handlers.doctor import (
    DEFAULT_IGNORE_LABEL,
    _parse_iso_ts,
    classify_zombies,
)


CATEGORIES = ('orphan', 'stalled', 'disabled', 'restored_entity',
              'unavailable_entity')

# Per-category truncation cap for table view (use --no-truncate to dump all).
TABLE_TOP_N = 20


def _fetch_all(hass_url, hass_token):
    """Pull devices, entities, areas, config-entries and states.

    Returns dict {devices, entities, areas, config_entries, states} or None
    on websocket failure (we still try to fetch states even if WS fails so
    restored entities can be surfaced).
    """
    devices, entities, areas = [], [], []
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

    # config_entries via REST (websocket also exposes this, but REST is simpler
    # and we already use it in check_config_entries).
    config_entries = []
    try:
        ce = make_api_request(
            f"{hass_url}/api/config/config_entries/entry", hass_token)
        if isinstance(ce, list):
            config_entries = ce
    except Exception:
        pass

    states = []
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


def _build_lookups(data):
    """Build helper lookup tables from the raw registries."""
    area_by_id = {a.get('area_id'): a.get('name') for a in data['areas']
                  if a.get('area_id')}
    domain_by_entry = {ce.get('entry_id'): ce.get('domain')
                       for ce in data['config_entries'] if ce.get('entry_id')}

    state_by_eid = {s.get('entity_id', ''): s for s in data['states']}

    # Per-device enabled and disabled entity lists, plus most-recent last_changed.
    enabled_by_device = {}
    disabled_by_device = {}
    most_recent_by_device = {}
    for e in data['entities']:
        did = e.get('device_id')
        if not did:
            continue
        if e.get('disabled_by'):
            disabled_by_device.setdefault(did, []).append(e)
            continue
        enabled_by_device.setdefault(did, []).append(e)
        s = state_by_eid.get(e.get('entity_id', ''))
        if s:
            lc = s.get('last_changed') or s.get('last_updated')
            if lc:
                cur = most_recent_by_device.get(did)
                if cur is None or lc > cur:
                    most_recent_by_device[did] = lc

    # entity_id -> registry-entity (for restored-entity platform resolution).
    entity_reg_by_eid = {e.get('entity_id'): e for e in data['entities']
                         if e.get('entity_id')}

    return {
        'area_by_id': area_by_id,
        'domain_by_entry': domain_by_entry,
        'state_by_eid': state_by_eid,
        'enabled_by_device': enabled_by_device,
        'disabled_by_device': disabled_by_device,
        'most_recent_by_device': most_recent_by_device,
        'entity_reg_by_eid': entity_reg_by_eid,
    }


def _resolve_integration(device, domain_by_entry):
    """Resolve the real integration domain(s) for a device.

    Returns a comma-joined string of distinct domains, or None if no
    config_entries map to known domains.
    """
    ces = device.get('config_entries') or []
    domains = []
    seen = set()
    for entry_id in ces:
        d = domain_by_entry.get(entry_id)
        if d and d not in seen:
            seen.add(d)
            domains.append(d)
    if not domains:
        return None
    return ','.join(domains)


def _device_record(device, category, lookups):
    """Build a triage record for a device-level zombie."""
    did = device.get('id') or ''
    name = device.get('name_by_user') or device.get('name') or None
    area = lookups['area_by_id'].get(device.get('area_id')) if device.get('area_id') else None
    integration = _resolve_integration(device, lookups['domain_by_entry'])
    if not integration:
        # Manufacturer fallback only when config_entries lookup fails entirely.
        integration = device.get('manufacturer') or None

    enabled = lookups['enabled_by_device'].get(did, [])
    disabled = lookups['disabled_by_device'].get(did, [])

    last_seen = None
    if category in ('stalled',):
        last_seen = lookups['most_recent_by_device'].get(did)

    return {
        'category': category,
        'device_id': did,
        'name': name,
        'area': area,
        'integration': integration,
        'manufacturer': device.get('manufacturer'),
        'model': device.get('model'),
        'sw_version': device.get('sw_version'),
        'hw_version': device.get('hw_version'),
        'via_device_id': device.get('via_device_id'),
        'disabled_by': device.get('disabled_by'),
        'entities_enabled': len(enabled),
        'entities_disabled': len(disabled),
        'last_seen': last_seen,
        'entity_id': None,
        'platform': None,
        'friendly_name': None,
        'state': None,
        'last_changed': None,
        'unavailable_for_seconds': None,
        'device_name': name,
    }


def _unavailable_entity_record(state, ent_reg, dev_reg, lookups, now):
    """Build a triage record for an individually-unavailable entity.

    Mirrors the `restored_entity` schema with two extra fields:
    - `state`: the actual reported state ('unavailable' or 'unknown')
    - `unavailable_for_seconds`: how long the entity has been in that
      state (now - last_changed). Used to sort the table view so the
      stalest entries surface first.
    """
    eid = state.get('entity_id') or ''
    attrs = state.get('attributes') or {}
    reg = ent_reg or {}
    did = reg.get('device_id') or None
    platform = reg.get('platform') or None

    # device > entity area
    area = None
    if dev_reg:
        device_area_id = dev_reg.get('area_id')
        if device_area_id:
            area = lookups['area_by_id'].get(device_area_id)
    if not area:
        ent_area = reg.get('area_id')
        if ent_area:
            area = lookups['area_by_id'].get(ent_area)

    last_changed = state.get('last_changed') or state.get('last_updated')
    last_dt = _parse_iso_ts(last_changed)
    unavailable_for = None
    if last_dt is not None:
        unavailable_for = int((now - last_dt).total_seconds())

    # Integration: prefer the entity registry's config_entry → domain map,
    # then fall back to its `platform` (which is what HA shows in the UI).
    integration = None
    ce_id = reg.get('config_entry_id')
    if ce_id:
        integration = lookups['domain_by_entry'].get(ce_id)
    if not integration:
        integration = platform

    via_device_id = (dev_reg or {}).get('via_device_id')

    return {
        'category': 'unavailable_entity',
        'device_id': did,
        'name': attrs.get('friendly_name') or eid,
        'area': area,
        'integration': integration,
        'manufacturer': (dev_reg or {}).get('manufacturer'),
        'model': (dev_reg or {}).get('model'),
        'sw_version': (dev_reg or {}).get('sw_version'),
        'hw_version': (dev_reg or {}).get('hw_version'),
        'via_device_id': via_device_id,
        'disabled_by': reg.get('disabled_by'),
        'entities_enabled': None,
        'entities_disabled': None,
        'last_seen': last_changed,
        'entity_id': eid,
        'platform': platform,
        'friendly_name': attrs.get('friendly_name'),
        'state': state.get('state'),
        'last_changed': last_changed,
        'unavailable_for_seconds': unavailable_for,
        'device_name': (dev_reg or {}).get('name_by_user')
                        or (dev_reg or {}).get('name'),
    }


def _restored_entity_record(state, lookups):
    """Build a triage record for a restored entity."""
    eid = state.get('entity_id') or ''
    attrs = state.get('attributes') or {}
    reg = lookups['entity_reg_by_eid'].get(eid) or {}
    did = reg.get('device_id') or None
    # Real platform from entity registry, NOT entity_id prefix.
    platform = reg.get('platform') or None

    area = None
    if did:
        # device area > entity area
        device_area_id = None
        for d in lookups.get('_devices', []):  # not always passed; fallback below
            if d.get('id') == did:
                device_area_id = d.get('area_id')
                break
        if device_area_id:
            area = lookups['area_by_id'].get(device_area_id)
    if not area:
        ent_area = reg.get('area_id')
        if ent_area:
            area = lookups['area_by_id'].get(ent_area)

    last_seen = state.get('last_changed') or state.get('last_updated')

    return {
        'category': 'restored_entity',
        'device_id': did,
        'name': attrs.get('friendly_name') or eid,
        'area': area,
        'integration': platform,  # platform IS the integration for an entity
        'manufacturer': None,
        'model': None,
        'sw_version': None,
        'hw_version': None,
        'via_device_id': None,
        'disabled_by': None,
        'entities_enabled': None,
        'entities_disabled': None,
        'last_seen': last_seen,
        'entity_id': eid,
        'platform': platform,
        'friendly_name': attrs.get('friendly_name'),
        'state': None,
        'last_changed': last_seen,
        'unavailable_for_seconds': None,
        'device_name': None,
    }


def _build_records(data, classified, category_filter=None, now=None):
    """Produce the full list of enriched triage records, filtered by category."""
    if now is None:
        now = datetime.now(timezone.utc)
    lookups = _build_lookups(data)
    # stash devices for restored-entity area lookup
    lookups['_devices'] = data['devices']

    records = []
    if category_filter in (None, 'orphan'):
        for d in classified['orphans']:
            records.append(_device_record(d, 'orphan', lookups))
    if category_filter in (None, 'stalled'):
        for d in classified['stalled']:
            records.append(_device_record(d, 'stalled', lookups))
    if category_filter in (None, 'disabled'):
        for d in classified['disabled']:
            records.append(_device_record(d, 'disabled', lookups))
    if category_filter in (None, 'restored', 'restored_entity'):
        for s in classified['restored_entities']:
            records.append(_restored_entity_record(s, lookups))
    if category_filter in (None, 'unavailable_entity'):
        for tup in classified.get('unavailable_entities', []):
            s, ent_reg, dev_reg = tup
            records.append(
                _unavailable_entity_record(s, ent_reg, dev_reg, lookups, now))

    # Default sort: unavailable_entity by stalest first; everything else
    # keeps registry-order (already category-grouped at print time).
    records.sort(key=lambda r: (
        0 if r.get('category') == 'unavailable_entity' else 1,
        -(r.get('unavailable_for_seconds') or 0)
        if r.get('category') == 'unavailable_entity' else 0,
    ))

    return records


def _truncate(s, n):
    if s is None:
        return '-'
    s = str(s)
    if len(s) <= n:
        return s
    return s[: n - 1] + '…'


def _print_table(records, no_truncate):
    """Print records grouped by category, with per-category truncation."""
    if not records:
        click.echo('No zombie devices found.')
        return

    by_cat = {c: [] for c in CATEGORIES}
    for r in records:
        by_cat.setdefault(r['category'], []).append(r)

    cat_titles = {
        'orphan': 'Orphan devices (no enabled entities)',
        'stalled': 'Stalled devices (all entities unavailable)',
        'disabled': 'Disabled devices (user/integration disabled)',
        'restored_entity': 'Restored entities (integration no longer provides them)',
        'unavailable_entity': 'Unavailable entities (>15min, on healthy domains)',
    }

    total = len(records)
    click.echo()
    click.secho(f"=== Zombie Devices ({total} total) ===", bold=True)

    for cat in CATEGORIES:
        rows = by_cat.get(cat, [])
        if not rows:
            continue
        shown = rows if no_truncate else rows[:TABLE_TOP_N]
        suffix = ''
        if not no_truncate and len(rows) > TABLE_TOP_N:
            suffix = f"  (showing {TABLE_TOP_N} of {len(rows)} — use --no-truncate for all)"
        click.echo()
        click.secho(f"--- {cat_titles[cat]}: {len(rows)} ---{suffix}", bold=True)
        click.echo(
            f"{'NAME':<32} {'AREA':<18} {'INTEGRATION':<22} "
            f"{'MODEL':<22} {'LAST_SEEN':<22} ID"
        )
        click.echo('-' * 150)
        for r in shown:
            click.echo(
                f"{_truncate(r['name'], 32):<32} "
                f"{_truncate(r['area'], 18):<18} "
                f"{_truncate(r['integration'], 22):<22} "
                f"{_truncate(r['model'], 22):<22} "
                f"{_truncate(r['last_seen'], 22):<22} "
                f"{r['device_id'] or r['entity_id'] or '-'}"
            )
    click.echo()


def _print_json(records):
    click.echo(json.dumps(records, indent=2, default=str))


CSV_FIELDS = [
    'category', 'device_id', 'device_name', 'name', 'area', 'integration',
    'manufacturer', 'model', 'sw_version', 'hw_version', 'via_device_id',
    'disabled_by', 'entities_enabled', 'entities_disabled', 'last_seen',
    'entity_id', 'platform', 'friendly_name',
    'state', 'last_changed', 'unavailable_for_seconds',
]


def _print_csv(records):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for r in records:
        writer.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in CSV_FIELDS})
    click.echo(buf.getvalue(), nl=False)


def get_zombie_devices(format_type='table', category=None, no_truncate=False,
                       ignore_label=None):
    """Triage entry point for `hactl get zombie-devices`."""
    HASS_URL, HASS_TOKEN = load_config()

    # Normalise --category alias.
    if category == 'restored':
        category = 'restored_entity'
    if category and category not in CATEGORIES:
        raise click.ClickException(
            f"Unknown category: {category}. "
            f"Choose one of: orphan, stalled, disabled, restored, "
            f"unavailable_entity")

    if ignore_label is None:
        ignore_label = os.environ.get(
            'HACTL_IGNORE_LABEL', DEFAULT_IGNORE_LABEL)

    data = _fetch_all(HASS_URL, HASS_TOKEN)
    if not data['ws_ok']:
        click.secho(
            'Warning: could not fetch device/entity registry over websocket; '
            'orphan/stalled/disabled categories will be empty.',
            fg='yellow', err=True)

    now = datetime.now(timezone.utc)
    classified = classify_zombies(
        data['devices'], data['entities'], data['states'],
        ignore_label=ignore_label, now=now)

    records = _build_records(
        data, classified, category_filter=category, now=now)

    if format_type == 'json':
        _print_json(records)
    elif format_type == 'csv':
        _print_csv(records)
    elif format_type == 'yaml':
        from hactl.core import json_to_yaml
        click.echo(json_to_yaml(records))
    else:
        _print_table(records, no_truncate=no_truncate)
