# `hactl delete`

Generic, kubectl-style deletion for Home Assistant resources. Mirrors
the verb/resource shape of `hactl get`. Supports a singular form (one
record by id), a plural form (filter-driven bulk), and a declarative
manifest form (`-f file.json` or `-f -` from stdin).

> **DESTRUCTIVE.** `hactl delete` removes records from Home Assistant's
> registries. There is **no undo** — HA does not support deletion
> rollback. The audit log written on every real run is forensic
> evidence, not a transaction log.

## Hard rules

1. **Default is dry-run.** Without `--yes`, every invocation prints the
   planned deletion set and exits without touching HA.
2. **Audit log always.** When something gets deleted, a JSON snapshot of
   the pre-delete registry state is written to
   `/tmp/hactl-delete-<ts>.json` (or `--audit <path>`). `--force` does
   **not** bypass the audit log.
3. **Safety predicate** refuses deletes (without `--force`) when the
   parent `config_entry.state == 'loaded'` AND the target entity has had
   any non-dead state in the last 7 days, or when the target device is
   `disabled_by` set (intentional disablement is not garbage).
4. **Live-state predicate** (entity-level) refuses (without `--force`)
   when the entity's CURRENT state is not in `('unavailable', 'unknown',
   None)` — i.e., it's a working sensor. Bulk forms HARD-REFUSE the
   live record and continue with the rest. Singular form (the operator
   named the entity by id) instead prompts y/N. See *The
   iPhone-12-Pro lesson* below.
5. **`--limit` cap** (default 50) bounds bulk batches. `--force`
   bypasses every safety predicate (including live-state) AND the limit.

## Synopsis

```text
# Singular by id
hactl delete device <id-or-name>
hactl delete entity <entity_id>
hactl delete config-entry <entry_id>

# Plural by filter
hactl delete devices --filter <key>=<value>
hactl delete entities --filter <key>=<value>
hactl delete config-entries --filter <key>=<value>

# Declarative input
hactl delete -f deletions.json
hactl delete -f -                 # stdin

# Common flags (all forms)
[--dry-run] [--yes] [--limit N] [--force] [--audit PATH] [--quiet]
```

### Resource kinds (PR scope)

| Kind | WebSocket call | Notes |
|------|----------------|-------|
| `device` | `config/device_registry/remove_config_entry` per `config_entries[*]` | HA auto-removes the device once its last entry is detached. |
| `entity` | `config/entity_registry/remove` | Works on any registry entity. Restored-only entities (in `/api/states` but not `entity_registry`) cannot be deleted this way — clear the recorder or remove the parent integration. |
| `config-entry` | `config_entries/delete` | Cascades to all owned devices + entities. Highest blast radius — predicate is strict. |

`automation`, `script`, `area`, `dashboard` are intentionally **out of
scope** for this PR.

### Filter keys

| Resource | Supported `--filter` keys |
|----------|----------------------------|
| `devices` | `category={orphan,stalled,disabled}`, `integration=<domain>`, `manufacturer=<substr>`, `area=<id>`, `disabled_by=<value\|none>` |
| `entities` | `platform=<str>`, `domain=<sensor\|binary_sensor\|...>`, `disabled_by=<value\|none>`, `device_id=<id>`, `restored=true` (plus `--state-only unavailable` flag for the recommended zombie-cleanup pattern) |
| `config-entries` | `state=<loaded\|not_loaded\|...>`, `domain=<str>`, `source=<user\|integration_discovery\|...>` |

Multiple `--filter` flags are AND-combined.

### Manifest format

A JSON array of objects. Either explicit `{kind, id}` or shapes coming
straight from `hactl get zombie-devices -o json` (which uses
`device_id` / `entity_id` / `entry_id`):

```json
[
  {"kind": "device", "id": "1a2b..."},
  {"kind": "entity", "id": "sensor.foo"},
  {"kind": "config-entry", "id": "abc..."}
]
```

```json
[
  {"category": "orphan",          "device_id": "1a2b..."},
  {"category": "restored_entity", "entity_id": "sensor.foo"}
]
```

## Common workflows

### 1. Zombie cleanup (recommended path)

```bash
# Inspect.
hactl get zombie-devices --category orphan

# Pipe a manifest through `delete` in dry-run.
hactl get zombie-devices -o json --category orphan \
  | hactl delete -f - --dry-run

# Commit.
hactl get zombie-devices -o json --category orphan \
  | hactl delete -f - --yes --limit 200 --audit ~/zombie-purge.json
```

### 2. Drop one dead integration in a single call

```bash
hactl get integrations --format json \
  | jq -r '.integrations[] | select(.state=="not_loaded") | .entry_id'

hactl delete config-entry <entry_id> --dry-run
hactl delete config-entry <entry_id> --yes
```

This is the killer one-shot for cases like `unifi default` — one
config-entry delete cascades to dozens of dead devices+entities.

### 3. Drop everything from a stale platform

```bash
hactl delete entities --filter platform=tibber_prices --dry-run
hactl delete entities --filter platform=tibber_prices --yes --limit 100
```

### 3b. Zombie entity cleanup with `--state-only unavailable` (recommended)

For the new HAGHS-parity `unavailable_entity` category, the safe path
filters out live entities BEFORE the safety predicate ever sees them:

```bash
hactl delete entities --filter platform=mobile_app \
                      --state-only unavailable --dry-run
hactl delete entities --filter platform=mobile_app \
                      --state-only unavailable --yes --limit 200
```

This is strictly safer than `--force` for the common
"delete-zombies-by-pattern" workflow: `--state-only unavailable` drops
live entities at filter time, so the audit log only contains records
that were genuinely dead.

## The iPhone-12-Pro lesson (and why the live-state predicate exists)

A real incident: a bulk delete keyed on `platform=mobile_app` caught
`sensor.andreas_iphone_12_pro_battery_level` — an active sensor
reporting `100` — and removed it because the pattern matched. There was
no signal in the pattern that distinguished the live sensor from the
dead ones around it.

The live-state predicate now refuses that exact mistake:

```text
$ hactl delete entity sensor.andreas_iphone_12_pro_battery_level --dry-run
REFUSED: entity 'sensor.andreas_iphone_12_pro_battery_level' has live state '100' (not unavailable/unknown).
Deleting an entity with active state usually means you're deleting a working sensor.
If you really want to delete it, pass --force.
```

Three rules to internalise:

1. **Never delete an entity by pattern alone.** Always pair `--filter`
   with `--state-only unavailable` (or with `--category orphan` /
   `--category stalled` on the device-level forms).
2. **The singular form gets a y/N prompt** — you named the resource by
   id, so the operator-friction model is "remind, don't refuse".
3. **`--force` exists** for the rare case where you really do want to
   delete a working sensor (e.g. you're replacing the device and need
   the old entity_id to free up). The audit log is still written.

### 4. Targeted single-record delete

```bash
hactl delete device "Living Room Lamp" --dry-run
hactl delete device "Living Room Lamp" --yes
```

## Output

Every run prints a plan table:

```text
=== Delete plan (3 records) ===
  config-entry=1, device=1, entity=1

KIND           ID                                               NAME / SUMMARY
--------------------------------------------------------------------------------
device         dev_orphan                                       Orphan Device
entity         sensor.orphan_temp                               sensor.orphan_temp
config-entry   ce_dead                                          oldintegration / Old [not_loaded]

DRY-RUN (default). Pass --yes to actually delete or --dry-run to silence this notice.
```

On a real run, per-record progress is printed as each WebSocket call
completes, and a final summary points at the audit log:

```text
  deleted: device dev_orphan
  deleted: entity sensor.orphan_temp
  deleted: config-entry ce_dead

Audit log: /tmp/hactl-delete-20260513T091245Z.json
Result: 3 deleted, 0 failed.
```

## Audit log shape

```json
{
  "timestamp": "2026-05-13T09:12:45+00:00",
  "hactl_version": "1.1.1",
  "user": "mu",
  "host": "host.example",
  "platform": "macOS-...",
  "invocation": ["hactl", "delete", "device", "dev_orphan", "--yes"],
  "records": [
    {
      "kind": "device",
      "id": "dev_orphan",
      "pre_state": { "...full registry record..." },
      "result": "deleted",
      "error": null
    }
  ]
}
```

This is the **only** rollback evidence — you can read the `pre_state`
fields and recreate registry entries by hand or via the UI. There is
no `hactl undelete`.

## Rollback

There is no rollback. HA's registry is the source of truth and provides
no undelete API. If you deleted the wrong thing:

1. Open the audit log; locate the `pre_state` for the affected record.
2. For `device` / `entity`: the integration that owned the record will
   re-create it on next reload if it still exists. Try
   `hactl get integrations` to confirm the entry is still loaded, then
   restart that integration in the HA UI.
3. For `config-entry`: re-add the integration via the HA UI. Devices
   and entities will be re-discovered, but historical state in the
   recorder is preserved (entity_ids will match).

## Troubleshooting

- **"REFUSED: entity 'X' has live state 'Y'"** — Live-state predicate
  triggered. The entity is currently reporting a real value, not
  `unavailable`/`unknown`. Either re-target by id with `--state-only
  unavailable`, narrow the filter, or pass `--force` if you really do
  want to delete a working sensor.
- **"Refusing to delete N entity(s) with live state in a bulk
  operation"** — Same predicate, bulk path. The live records are
  dropped from the plan; the rest proceed. To include them, add
  `--force` (audit still written).
- **"safety predicate blocked N record(s)"** — Targets had recent
  activity on a loaded integration. Re-check why you're deleting them;
  if you really mean it, add `--force`.
- **"batch size N exceeds --limit M"** — Pass `--limit <N>` or
  `--force`.
- **"entity is not in entity_registry (restored-from-state only)"** — A
  restored entity that exists only in `/api/states` cannot be removed
  via `entity_registry/remove`. Clear it from the recorder
  (`hactl k8s ...` workflows) or remove its old parent integration.
- **WebSocket connect failed** — Verify `HASS_URL` / `HASS_TOKEN` and
  reachability; `hactl doctor` is the entry point.

## See also

- `docs/get-zombie-devices.md` — triage doc; produces the JSON shape
  `hactl delete -f -` consumes.
- `hactl doctor --check zombie_devices` — quick sweep that surfaces
  what `delete` should later prune.
