"""
Health check handler for hactl doctor command
"""

import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
import click
from hactl.core import load_config, make_api_request
from hactl.core.websocket import WebSocketClient


# Domains that are inherently static and shouldn't be flagged as stale
STATIC_DOMAINS = frozenset([
    'persistent_notification', 'zone', 'person', 'scene', 'input_boolean',
    'input_number', 'input_text', 'input_select', 'input_datetime',
    'input_button', 'counter', 'timer', 'group', 'sun',
])

# Domains where 'unknown' state is expected (action-type entities that have never triggered)
EXPECTED_UNKNOWN_DOMAINS = frozenset([
    'button', 'event', 'scene', 'notify', 'stt', 'tts', 'ai_task',
])

# Keywords in entity_id that indicate mobile devices (typically off-network)
MOBILE_KEYWORDS = frozenset([
    'iphone', 'ipad', 'macbook', 'android', 'watch', 'tablet', 'mobile',
])

# Keywords in entity_id that indicate appliances (typically powered off)
APPLIANCE_KEYWORDS = frozenset([
    'washing_machine', 'tumble_dryer', 'dryer', 'dishwasher', 'oven',
    'neff_oven',
])

# Keywords for Echo/Alexa devices (alarm/reminder/timer sensors always unavailable)
ECHO_KEYWORDS = frozenset([
    'echo_dot', 'echo_show', 'fire_tv', 'echo_', '_echo_',
])

# Keywords for UniFi network switch PoE port controls
UNIFI_KEYWORDS = frozenset([
    '_sw_', 'sw_24', 'sw_16', 'sw_8', 'usw_',
])

# Keywords for solar inverter entities (unavailable at night)
SOLAR_INVERTER_PREFIXES = frozenset([
    's1_ch', 's2_ch', 's3_ch', 's1_limit', 's2_limit', 's3_limit',
    's1_voltage', 's1_current', 's1_power', 's1_frequency', 's1_powerfactor',
    's1_reactivepower', 's1_powerdc', 's1_yieldday', 's1_yieldtotal',
    's1_temperature', 's1_efficiency',
    's2_voltage', 's2_current', 's2_power', 's2_frequency', 's2_powerfactor',
    's2_reactivepower', 's2_powerdc', 's2_yieldday', 's2_yieldtotal',
    's2_temperature', 's2_efficiency',
    's3_voltage', 's3_current', 's3_power', 's3_frequency', 's3_powerfactor',
    's3_reactivepower', 's3_powerdc', 's3_yieldday', 's3_yieldtotal',
    's3_temperature', 's3_efficiency',
])

# Keywords for AirPlay endpoints (unavailable when device is off)
AIRPLAY_KEYWORDS = frozenset([
    'airplay', '_airplay',
])

# Keywords for Frigate camera review/person entities
CAMERA_REVIEW_KEYWORDS = frozenset([
    'review_status', '_person',
])

# Domains for Frigate camera review/person entities (only match image domain for _person)
CAMERA_REVIEW_DOMAINS = frozenset([
    'image',
])

BATTERY_CRITICAL_THRESHOLD = 15
BATTERY_WARNING_THRESHOLD = 30
STALE_HOURS = 24
ERROR_LOG_WARNING_THRESHOLD = 20


def _finding(status, message):
    """Create a single finding dict."""
    return {'status': status, 'message': message}


def _check_result(name, findings):
    """Create a check result dict, deriving overall status from findings."""
    severity_order = ['critical', 'warning', 'info', 'ok']
    overall = 'ok'
    for f in findings:
        if severity_order.index(f['status']) < severity_order.index(overall):
            overall = f['status']
    return {'name': name, 'status': overall, 'findings': findings}


def check_api(hass_url, hass_token):
    """Check API connectivity."""
    try:
        result = make_api_request(f"{hass_url}/api/", hass_token)
        msg = result.get('message', 'API responding')
        return _check_result('API Connectivity', [_finding('ok', msg)])
    except click.ClickException as e:
        return _check_result('API Connectivity', [
            _finding('critical', f"API unreachable: {e.format_message()}")
        ])


def _classify_entity(entity_id, state_val):
    """Classify an unavailable/unknown entity into a category.

    Returns one of the category keys used in check_unavailable().
    """
    domain = entity_id.split('.')[0] if '.' in entity_id else ''
    eid_lower = entity_id.lower()
    name_part = entity_id.split('.', 1)[1] if '.' in entity_id else entity_id

    # Action-type entities in 'unknown' state — expected, never triggered
    if state_val == 'unknown' and domain in EXPECTED_UNKNOWN_DOMAINS:
        return 'expected_unknown'

    # Mobile devices off-network
    if state_val == 'unavailable' and any(kw in eid_lower for kw in MOBILE_KEYWORDS):
        return 'mobile'

    # Appliances powered off (both unavailable and unknown — program sensors are unknown when off)
    if any(kw in eid_lower for kw in APPLIANCE_KEYWORDS):
        return 'appliance'

    # Echo/Alexa devices — alarm/reminder/timer sensors always unavailable
    if state_val == 'unavailable' and any(kw in eid_lower for kw in ECHO_KEYWORDS):
        return 'echo_alexa'

    # UniFi network switch PoE port controls
    if any(kw in eid_lower for kw in UNIFI_KEYWORDS):
        return 'unifi_switches'

    # Solar inverter entities — unavailable at night
    if any(name_part.startswith(prefix) or name_part.startswith(prefix.replace('_', '', 1))
           for prefix in SOLAR_INVERTER_PREFIXES):
        return 'solar_inverter'

    # AirPlay endpoints — unavailable when device is off
    if state_val == 'unavailable' and any(kw in eid_lower for kw in AIRPLAY_KEYWORDS):
        return 'airplay'

    # Frigate camera review status and person image entities
    if any(kw in eid_lower for kw in CAMERA_REVIEW_KEYWORDS):
        if 'review_status' in eid_lower or domain in CAMERA_REVIEW_DOMAINS:
            return 'camera_review'

    return 'truly_unavailable'


def _get_device_group(entity_id):
    """Extract a meaningful device group name from an entity_id.

    Uses the first two underscore segments for better grouping,
    e.g. 'sensor.shelly_kitchen_power' -> 'shelly_kitchen'
    """
    name_part = entity_id.split('.', 1)[1] if '.' in entity_id else entity_id
    parts = name_part.split('_')
    if len(parts) >= 2:
        return '_'.join(parts[:2])
    return parts[0] if parts else name_part


# INFO category labels for output
_INFO_CATEGORY_LABELS = {
    'expected_unknown': ('action entities in expected \'unknown\' state', True),
    'mobile': ('mobile device entities unavailable (likely off-network)', False),
    'appliance': ('appliance entities unavailable (likely powered off)', False),
    'echo_alexa': ('Echo/Alexa entities unavailable (alarm/reminder/timer not set)', False),
    'unifi_switches': ('UniFi switch PoE port entities (expected for port controls)', False),
    'solar_inverter': ('solar inverter entities unavailable (offline/nighttime)', False),
    'airplay': ('AirPlay endpoint entities unavailable (devices off)', False),
    'camera_review': ('camera review/person entities in expected \'unknown\' state', False),
}


def check_unavailable(states):
    """Check for entities with unavailable/unknown state, with smart categorization."""
    categories = {
        'expected_unknown': [],
        'mobile': [],
        'appliance': [],
        'echo_alexa': [],
        'unifi_switches': [],
        'solar_inverter': [],
        'airplay': [],
        'camera_review': [],
        'truly_unavailable': [],
    }
    healthy_count = 0

    for s in states:
        state_val = s.get('state', '')
        if state_val in ('unavailable', 'unknown'):
            eid = s.get('entity_id', '?')
            cat = _classify_entity(eid, state_val)
            categories[cat].append(eid)
        else:
            healthy_count += 1

    findings = []

    # INFO categories
    for cat_key, (label, show_domains) in _INFO_CATEGORY_LABELS.items():
        entities = categories.get(cat_key, [])
        if not entities:
            continue
        if show_domains:
            domains = set()
            for eid in entities:
                d = eid.split('.')[0] if '.' in eid else ''
                if d:
                    domains.add(d)
            domain_list = ', '.join(sorted(domains))
            findings.append(_finding('info',
                f"{len(entities)} {label} ({domain_list})"))
        else:
            findings.append(_finding('info',
                f"{len(entities)} {label}"))

    # Truly unavailable — WARNING, grouped by device prefix
    truly = categories['truly_unavailable']
    if truly:
        groups = {}
        for eid in truly:
            prefix = _get_device_group(eid)
            groups.setdefault(prefix, []).append(eid)

        sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]))

        findings.append(_finding('warning',
            f"Truly unavailable: {len(truly)} entities across {len(groups)} device groups"))

        for prefix, eids in sorted_groups[:10]:
            findings.append(_finding('warning',
                f"  {prefix}: {len(eids)} entities"))

        if len(sorted_groups) > 10:
            remaining = sum(len(eids) for _, eids in sorted_groups[10:])
            findings.append(_finding('warning',
                f"  ... and {len(sorted_groups) - 10} more groups ({remaining} entities)"))

    # Healthy count
    if healthy_count > 0:
        findings.append(_finding('ok', f"{healthy_count} entities healthy"))

    if not findings:
        findings.append(_finding('ok', 'All entities available'))

    return _check_result('Unavailable Entities', findings)


def check_batteries(states):
    """Check for low battery devices."""
    findings = []
    for s in states:
        attrs = s.get('attributes', {})
        if attrs.get('device_class') != 'battery':
            continue
        try:
            level = float(s.get('state', ''))
        except (ValueError, TypeError):
            continue
        eid = s.get('entity_id', '?')
        if level < BATTERY_CRITICAL_THRESHOLD:
            findings.append(_finding('critical', f"{eid} - {int(level)}%"))
        elif level < BATTERY_WARNING_THRESHOLD:
            findings.append(_finding('warning', f"{eid} - {int(level)}%"))
    if not findings:
        return _check_result('Low Battery Devices', [
            _finding('ok', 'All batteries above 30%')
        ])
    return _check_result('Low Battery Devices', findings)


def _fetch_plain_text(url, token):
    """Fetch a plain-text API endpoint (e.g., /api/error_log)."""
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req) as response:
        return response.read().decode()


def check_error_log(hass_url, hass_token):
    """Analyze error log for issues."""
    try:
        log_text = _fetch_plain_text(f"{hass_url}/api/error_log", hass_token)
    except Exception:
        return _check_result('Error Log', [
            _finding('warning', 'Could not retrieve error log')
        ])

    lines = log_text.strip().split('\n') if log_text.strip() else []
    error_lines = [l for l in lines if 'ERROR' in l.upper()]
    error_count = len(error_lines)

    if error_count == 0:
        return _check_result('Error Log', [_finding('ok', 'No errors in log')])

    # Count errors by integration
    integration_counts = {}
    pattern = re.compile(r'homeassistant\.components\.(\w+)')
    for line in error_lines:
        m = pattern.search(line)
        if m:
            domain = m.group(1)
            integration_counts[domain] = integration_counts.get(domain, 0) + 1

    findings = []
    status = 'warning' if error_count > ERROR_LOG_WARNING_THRESHOLD else 'info'
    findings.append(_finding(status, f"{error_count} errors found in current log"))

    for domain, count in sorted(integration_counts.items(), key=lambda x: -x[1])[:3]:
        findings.append(_finding('info', f"Top: homeassistant.components.{domain} ({count} errors)"))

    return _check_result('Error Log', findings)


def _post_json(url, token, data=None):
    """Make a POST request returning parsed JSON."""
    req = urllib.request.Request(url, method='POST')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'application/json')
    req.data = json.dumps(data or {}).encode('utf-8')
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def check_config(hass_url, hass_token):
    """Validate Home Assistant configuration."""
    try:
        result = _post_json(f"{hass_url}/api/config/core/check_config", hass_token)
        errors = result.get('errors', None) or result.get('error', None)
        if errors:
            return _check_result('Configuration', [
                _finding('critical', f"Config errors: {errors}")
            ])
        res = result.get('result', 'valid')
        return _check_result('Configuration', [
            _finding('ok', f"Configuration {res}")
        ])
    except Exception as e:
        return _check_result('Configuration', [
            _finding('warning', f"Could not validate config: {e}")
        ])


def check_stale(states):
    """Check for entities that haven't updated recently."""
    now = datetime.now(timezone.utc)
    findings = []
    for s in states:
        eid = s.get('entity_id', '')
        domain = eid.split('.')[0] if '.' in eid else ''
        if domain in STATIC_DOMAINS:
            continue
        last_changed = s.get('last_changed', s.get('last_updated', ''))
        if not last_changed:
            continue
        try:
            ts = datetime.fromisoformat(last_changed.replace('Z', '+00:00'))
            delta = now - ts
            hours = delta.total_seconds() / 3600
            if hours > STALE_HOURS:
                days = delta.days
                if days >= 1:
                    age_str = f"{days} day{'s' if days != 1 else ''} ago"
                else:
                    age_str = f"{int(hours)} hours ago"
                findings.append(_finding('warning', f"{eid} - last changed {age_str}"))
        except (ValueError, TypeError):
            continue

    if not findings:
        return _check_result('Stale Entities', [
            _finding('ok', 'All entities recently updated')
        ])
    return _check_result('Stale Entities', findings)


def check_version(hass_url, hass_token):
    """Get version and system info."""
    try:
        config = make_api_request(f"{hass_url}/api/config", hass_token)
        version = config.get('version', 'unknown')
        location = config.get('location_name', 'unknown')
        tz = config.get('time_zone', 'unknown')
        components = config.get('components', [])
        return {
            'version': version,
            'location': location,
            'timezone': tz,
            'components_count': len(components),
            'check': _check_result('Version & System Info', [
                _finding('info', f"Version: {version}"),
                _finding('info', f"Location: {location}, TZ: {tz}"),
                _finding('info', f"{len(components)} components loaded"),
            ])
        }
    except click.ClickException:
        return {
            'version': 'unknown',
            'location': 'unknown',
            'timezone': 'unknown',
            'components_count': 0,
            'check': _check_result('Version & System Info', [
                _finding('warning', 'Could not retrieve system info')
            ])
        }


def check_entity_availability_by_domain(states):
    """Group truly unavailable entities by integration domain.

    Uses _classify_entity to exclude all INFO categories (expected unknowns,
    mobile devices, appliances, Echo/Alexa, UniFi, solar, AirPlay, cameras).
    Only counts entities classified as 'truly_unavailable'.

    NOTE: This is the entity-level rollup. It will NOT surface a failed
    integration setup (e.g. setup_retry, setup_error) because such an
    integration produces no entities to count. Use check_config_entries()
    for integration-level failures.
    """
    domain_unavail = {}
    domain_totals = {}
    for s in states:
        eid = s.get('entity_id', '')
        domain = eid.split('.')[0] if '.' in eid else ''
        if not domain:
            continue
        domain_totals[domain] = domain_totals.get(domain, 0) + 1
        state_val = s.get('state', '')
        if state_val not in ('unavailable', 'unknown'):
            continue
        # Only count truly unavailable entities
        if _classify_entity(eid, state_val) == 'truly_unavailable':
            domain_unavail[domain] = domain_unavail.get(domain, 0) + 1

    findings = []
    for domain in sorted(domain_unavail.keys()):
        count = domain_unavail[domain]
        total = domain_totals[domain]
        pct = int(count / total * 100) if total > 0 else 0
        findings.append(_finding('warning',
            f"{domain}: {count}/{total} unavailable ({pct}%)"))

    domains_ok = [d for d in domain_totals if d not in domain_unavail]
    # Don't list purely action-type domains as "ok" — they're just not relevant
    domains_ok = [d for d in domains_ok if d not in EXPECTED_UNKNOWN_DOMAINS]
    if domains_ok and len(domains_ok) <= 10:
        for d in sorted(domains_ok):
            findings.append(_finding('ok', f"{d}: all entities available"))
    elif domains_ok:
        findings.append(_finding('ok', f"{len(domains_ok)} domains with all entities available"))

    if not findings:
        findings.append(_finding('ok', 'No integration issues detected'))

    return _check_result('Entity Availability by Domain', findings)


# Severity mapping for config-entry states.
# CRIT: integration is broken and won't recover without intervention.
# WARN: integration is in a transient or user-suppressed-not-loaded state.
_CONFIG_ENTRY_CRIT_STATES = frozenset(['setup_error', 'failed_unload', 'migration_error'])
_CONFIG_ENTRY_WARN_STATES = frozenset(['setup_retry', 'setup_in_progress', 'not_loaded'])


def check_config_entries(hass_url, hass_token):
    """Check Home Assistant config entries (integrations) for failed setup states.

    Uses the REST endpoint /api/config/config_entries/entry, which (since
    HA 2024.x) includes `reason`, `disabled_by`, and `source` fields.
    Entries with `disabled_by` set or `source == "ignore"` are user-suppressed
    and ignored. Remaining non-`loaded` entries are mapped to severities
    via _CONFIG_ENTRY_CRIT_STATES / _CONFIG_ENTRY_WARN_STATES.
    """
    try:
        entries = make_api_request(
            f"{hass_url}/api/config/config_entries/entry", hass_token)
    except click.ClickException as e:
        return _check_result('Integrations', [
            _finding('warning', f"Could not fetch config entries: {e.format_message()}")
        ])
    except Exception as e:
        return _check_result('Integrations', [
            _finding('warning', f"Could not fetch config entries: {e}")
        ])

    if not isinstance(entries, list):
        return _check_result('Integrations', [
            _finding('warning', 'Unexpected config_entries response shape')
        ])

    findings = []
    loaded = 0
    suppressed = 0

    for entry in entries:
        state = entry.get('state', 'unknown')
        if state == 'loaded':
            loaded += 1
            continue

        # Suppress user-disabled or user-ignored entries (discovery noise).
        if entry.get('disabled_by') or entry.get('source') == 'ignore':
            suppressed += 1
            continue

        domain = entry.get('domain', 'unknown')
        title = entry.get('title', '?') or '?'
        reason = entry.get('reason')

        if state in _CONFIG_ENTRY_CRIT_STATES:
            severity = 'critical'
        elif state in _CONFIG_ENTRY_WARN_STATES:
            severity = 'warning'
        else:
            # Unknown non-loaded state — treat as warning, surface verbatim.
            severity = 'warning'

        msg = f"{domain} ({title}): {state}"
        if reason:
            msg += f" — {reason}"
        findings.append(_finding(severity, msg))

    if not findings:
        summary = f"{loaded} integrations loaded"
        if suppressed:
            summary += f", {suppressed} user-suppressed"
        findings.append(_finding('ok', summary))
    else:
        findings.append(_finding('info',
            f"{loaded} loaded, {suppressed} user-suppressed"))

    return _check_result('Integrations', findings)


# Threshold above which the per-category zombie count is escalated to WARN.
# These are tuned to be permissive — most installs will accumulate some orphan
# devices (failed pairings, replaced hardware) without operational impact.
# The check is primarily a visibility tool, not a hard gate.
ZOMBIE_DEVICE_WARN_THRESHOLD = 25
ZOMBIE_RESTORED_ENTITY_WARN_THRESHOLD = 50
ZOMBIE_TOP_N = 5


def _fetch_registries(hass_url, hass_token):
    """Pull device + entity registry over websocket. Returns (devices, entities) or None on failure."""
    ws = WebSocketClient(hass_url, hass_token)
    try:
        ws.connect()
        devices = ws.call('config/device_registry/list')
        entities = ws.call('config/entity_registry/list')
        ws.close()
    except Exception:
        try:
            ws.close()
        except Exception:
            pass
        return None
    if not isinstance(devices, list) or not isinstance(entities, list):
        return None
    return devices, entities


def check_zombie_devices(hass_url, hass_token, states):
    """Identify zombie devices and zombie entities.

    Three device-level categories and one entity-level category, all reported
    as separate sub-counts in a single section:

      1. Orphan devices       — device has zero enabled entities (entities
                                may exist but all are disabled_by set, or
                                no entities at all).
      2. Stalled devices      — device has enabled entities, but ALL of them
                                are currently 'unavailable' or 'unknown'.
                                Strong signal the underlying device is gone.
      3. Disabled devices     — device.disabled_by is set (user or
                                integration disabled the whole device).
      4. Restored entities    — entity's state attributes contain
                                'restored: true', meaning HA loaded the
                                state from history because the integration
                                no longer provides this entity. Most
                                commonly seen on device_tracker / sensor
                                from removed integrations.

    Categories 2 and 3 can overlap, and (1) is reported strictly
    (no enabled entities at all). Top-N example per category is shown.
    Total count is the sum across all four categories (with overlap kept,
    matching what users see when scanning HA's Devices page + Watchman).
    """
    registries = _fetch_registries(hass_url, hass_token)
    if registries is None:
        return _check_result('Zombie Devices', [
            _finding('warning', 'Could not fetch device/entity registry over websocket')
        ])

    devices, entities = registries
    state_by_eid = {s.get('entity_id', ''): s for s in (states or [])}

    # Build device -> enabled-entities map
    enabled_entities_by_device = {}
    for e in entities:
        did = e.get('device_id')
        if not did:
            continue
        if e.get('disabled_by'):
            continue
        enabled_entities_by_device.setdefault(did, []).append(e)

    orphans = []
    stalled = []
    disabled_devs = []

    for d in devices:
        did = d.get('id')
        if not did:
            continue
        ents = enabled_entities_by_device.get(did, [])

        if d.get('disabled_by'):
            disabled_devs.append(d)
            continue

        if not ents:
            orphans.append(d)
            continue

        # Stalled: all enabled entities currently unavailable/unknown
        all_dead = True
        any_with_state = False
        for e in ents:
            s = state_by_eid.get(e.get('entity_id', ''))
            if not s:
                continue
            any_with_state = True
            if s.get('state') not in ('unavailable', 'unknown'):
                all_dead = False
                break
        if any_with_state and all_dead:
            stalled.append(d)

    # Restored entities (state.attributes.restored == True). Integration is
    # no longer providing this entity; HA is keeping it from history.
    restored_entities = []
    for s in (states or []):
        if s.get('attributes', {}).get('restored'):
            restored_entities.append(s)

    findings = []
    total = len(orphans) + len(stalled) + len(disabled_devs) + len(restored_entities)

    def _device_label(d):
        name = d.get('name_by_user') or d.get('name') or '?'
        did = d.get('id', '') or ''
        domain = '?'
        ces = d.get('config_entries') or []
        if ces:
            # config_entries is a list of entry_ids; we don't have the
            # mapping here, so fall back to manufacturer for context.
            domain = d.get('manufacturer') or d.get('model') or '?'
        return f"{name} (id={did[:8]}, integration={domain})"

    def _entity_label(s):
        eid = s.get('entity_id', '?')
        domain = eid.split('.')[0] if '.' in eid else '?'
        return f"{eid} (integration={domain})"

    # Orphans
    if orphans:
        sev = 'warning' if len(orphans) > ZOMBIE_DEVICE_WARN_THRESHOLD else 'info'
        findings.append(_finding(sev,
            f"Orphan devices (no enabled entities): {len(orphans)}"))
        for d in orphans[:ZOMBIE_TOP_N]:
            findings.append(_finding('info', f"  {_device_label(d)}"))
        if len(orphans) > ZOMBIE_TOP_N:
            findings.append(_finding('info',
                f"  ... and {len(orphans) - ZOMBIE_TOP_N} more"))

    # Stalled
    if stalled:
        sev = 'warning' if len(stalled) > ZOMBIE_DEVICE_WARN_THRESHOLD else 'info'
        findings.append(_finding(sev,
            f"Stalled devices (all entities unavailable): {len(stalled)}"))
        for d in stalled[:ZOMBIE_TOP_N]:
            findings.append(_finding('info', f"  {_device_label(d)}"))
        if len(stalled) > ZOMBIE_TOP_N:
            findings.append(_finding('info',
                f"  ... and {len(stalled) - ZOMBIE_TOP_N} more"))

    # Disabled
    if disabled_devs:
        findings.append(_finding('info',
            f"Disabled devices (user/integration disabled): {len(disabled_devs)}"))
        for d in disabled_devs[:ZOMBIE_TOP_N]:
            findings.append(_finding('info', f"  {_device_label(d)}"))
        if len(disabled_devs) > ZOMBIE_TOP_N:
            findings.append(_finding('info',
                f"  ... and {len(disabled_devs) - ZOMBIE_TOP_N} more"))

    # Restored entities
    if restored_entities:
        sev = 'warning' if len(restored_entities) > ZOMBIE_RESTORED_ENTITY_WARN_THRESHOLD else 'info'
        findings.append(_finding(sev,
            f"Restored entities (integration no longer provides them): {len(restored_entities)}"))
        for s in restored_entities[:ZOMBIE_TOP_N]:
            findings.append(_finding('info', f"  {_entity_label(s)}"))
        if len(restored_entities) > ZOMBIE_TOP_N:
            findings.append(_finding('info',
                f"  ... and {len(restored_entities) - ZOMBIE_TOP_N} more"))

    if not findings:
        findings.append(_finding('ok', 'No zombie devices or entities detected'))
    else:
        findings.append(_finding('info',
            f"Total zombie items: {total} ({len(orphans)} orphan + "
            f"{len(stalled)} stalled + {len(disabled_devs)} disabled + "
            f"{len(restored_entities)} restored entities)"))

    return _check_result('Zombie Devices', findings)


def check_automations(states):
    """Check automation health."""
    now = datetime.now(timezone.utc)
    findings = []
    disabled = 0
    stale_automations = 0

    for s in states:
        eid = s.get('entity_id', '')
        if not eid.startswith('automation.'):
            continue
        name = s.get('attributes', {}).get('friendly_name', eid)
        state_val = s.get('state', '')

        if state_val == 'off':
            disabled += 1
            continue

        last_triggered = s.get('attributes', {}).get('last_triggered')
        if last_triggered:
            try:
                ts = datetime.fromisoformat(str(last_triggered).replace('Z', '+00:00'))
                delta = now - ts
                if delta.days >= 7:
                    stale_automations += 1
                    findings.append(_finding('warning',
                        f"{name} - hasn't triggered in {delta.days} days"))
            except (ValueError, TypeError):
                pass

    if disabled > 0:
        findings.insert(0, _finding('info', f"{disabled} automation{'s' if disabled != 1 else ''} disabled"))
    if not findings:
        findings.append(_finding('ok', 'All automations healthy'))

    return _check_result('Automation Health', findings)


SEVERITY_COLORS = {
    'critical': 'red',
    'warning': 'yellow',
    'info': 'cyan',
    'ok': 'green',
}

SEVERITY_LABELS = {
    'critical': 'CRIT',
    'warning': 'WARN',
    'info': 'INFO',
    'ok': 'OK  ',
}

ALL_CHECKS = [
    'api', 'unavailable', 'batteries', 'error_log', 'config',
    'stale', 'version', 'config_entries', 'entity_availability',
    'zombie_devices', 'automations',
]


def run_doctor(format_type='table', check_name=None):
    """Run health checks and produce a report."""
    HASS_URL, HASS_TOKEN = load_config()

    if check_name and check_name not in ALL_CHECKS:
        raise click.ClickException(
            f"Unknown check: {check_name}. Available: {', '.join(ALL_CHECKS)}")

    checks_to_run = [check_name] if check_name else ALL_CHECKS

    # Fetch states once if needed by any check
    states = None
    needs_states = {'unavailable', 'batteries', 'stale', 'entity_availability', 'automations', 'zombie_devices'}
    if needs_states & set(checks_to_run):
        try:
            states = make_api_request(f"{HASS_URL}/api/states", HASS_TOKEN)
        except click.ClickException as e:
            if format_type == 'json':
                click.echo(json.dumps({'error': f'Could not fetch states: {e.format_message()}'}, indent=2))
            else:
                click.secho(f"Error: Could not fetch states: {e.format_message()}", fg='red')
            return

    # Run checks
    results = []
    version_info = None

    for name in checks_to_run:
        if name == 'api':
            results.append(check_api(HASS_URL, HASS_TOKEN))
        elif name == 'unavailable':
            results.append(check_unavailable(states))
        elif name == 'batteries':
            results.append(check_batteries(states))
        elif name == 'error_log':
            results.append(check_error_log(HASS_URL, HASS_TOKEN))
        elif name == 'config':
            results.append(check_config(HASS_URL, HASS_TOKEN))
        elif name == 'stale':
            results.append(check_stale(states))
        elif name == 'version':
            version_info = check_version(HASS_URL, HASS_TOKEN)
            results.append(version_info['check'])
        elif name == 'config_entries':
            results.append(check_config_entries(HASS_URL, HASS_TOKEN))
        elif name == 'entity_availability':
            results.append(check_entity_availability_by_domain(states))
        elif name == 'zombie_devices':
            results.append(check_zombie_devices(HASS_URL, HASS_TOKEN, states))
        elif name == 'automations':
            results.append(check_automations(states))

    # Output
    if format_type == 'json':
        output = {
            'instance': HASS_URL,
            'checks': results,
        }
        if version_info:
            output['version'] = version_info['version']
        output['summary'] = _calculate_summary(results)
        click.echo(json.dumps(output, indent=2))
    else:
        _print_table_report(HASS_URL, version_info, results)


def _calculate_summary(results):
    """Calculate summary counts from check results.

    Overall health is based on actionable findings (critical/warning) only.
    INFO findings are informational and don't affect the health assessment.
    """
    counts = {'critical': 0, 'warning': 0, 'info': 0, 'ok': 0}
    for check in results:
        for f in check['findings']:
            counts[f['status']] += 1

    actionable = counts['critical'] + counts['warning']

    if counts['critical'] > 0:
        overall = 'CRITICAL'
    elif counts['warning'] > 0:
        overall = 'WARNING'
    else:
        overall = 'HEALTHY'

    return {**counts, 'actionable': actionable, 'overall': overall}


def _print_table_report(hass_url, version_info, results):
    """Print the health report in table format."""
    click.echo()
    click.secho("=== Home Assistant Health Report ===", bold=True)
    click.echo(f"  Instance: {hass_url}")
    if version_info:
        click.echo(f"  Version:  {version_info['version']}")
    click.echo()

    for check in results:
        finding_count = sum(1 for f in check['findings'] if f['status'] != 'ok')
        title = check['name']
        if finding_count > 0:
            title += f" ({finding_count} found)"
        click.secho(f"--- {title} ---", bold=True)

        for f in check['findings']:
            label = SEVERITY_LABELS[f['status']]
            color = SEVERITY_COLORS[f['status']]
            click.echo('  ', nl=False)
            click.secho(label, fg=color, nl=False)
            click.echo(f"  {f['message']}")
        click.echo()

    # Summary
    summary = _calculate_summary(results)
    click.secho("=== Summary ===", bold=True)
    click.echo(f"  Critical:   {summary['critical']}")
    click.echo(f"  Warnings:   {summary['warning']}")
    click.echo(f"  Info:       {summary['info']}")
    click.echo(f"  OK:         {summary['ok']}")
    click.echo(f"  Actionable: {summary['actionable']}")
    click.echo()

    overall = summary['overall']
    color = {'CRITICAL': 'red', 'WARNING': 'yellow', 'HEALTHY': 'green'}[overall]
    click.echo('  Overall Health: ', nl=False)
    click.secho(overall, fg=color, bold=True)
    click.echo()
