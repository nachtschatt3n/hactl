# `hactl get zombie-devices`

Triage-grade list of zombie devices and restored entities in your Home
Assistant install. Pair with `hactl doctor --check zombie_devices` (the
quick scan) when you actually want to walk through every record and
decide *remove / keep / fix-integration*.

**Read-only.** This command never deletes or modifies anything in
Home Assistant. Removing devices is still a manual UI action.

## Synopsis

```
hactl get zombie-devices [-o table|json|csv|yaml]
                         [--category orphan|stalled|disabled|restored|unavailable_entity]
                         [--no-truncate]
                         [--ignore-label LABEL]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `-o`, `-f`, `--format` | `table` | Output format. `json`/`csv` dump every record (no truncation). |
| `--category` | (all) | Filter to one category. `restored` is shorthand for `restored_entity`. |
| `--no-truncate` | off | Table mode: dump every row instead of the top-20-per-category default. |
| `--ignore-label` | `haghs_ignore` (env `HACTL_IGNORE_LABEL`) | Entity OR its parent device carrying this label is skipped from every category. Cross-tool compatible with HAGHS. |

## What's a zombie device?

There are five categories. Treat the question as: **"should I keep this
or remove it?"**

- **Orphan** — Device is in the registry but has zero enabled entities
  (either no entities at all, or every entity is `disabled_by` set).
  Usually a device that was renamed, re-paired, or partially removed.
  Almost always safe to delete; if a cluster of orphans shares the same
  `via_device_id`, the parent hub is the real culprit.
- **Stalled** — Device has enabled entities, but every one of them is
  currently `unavailable` or `unknown`. Strong signal the underlying
  hardware is gone (battery dead, unplugged, network changed, paired to
  a different controller). Check `last_seen` to decide.
- **Disabled** — `device.disabled_by` is set. Usually intentional
  (user turned off a Flic, an integration auto-disabled a stale sub-
  device). Generally safe to leave alone unless the count is climbing.
- **Restored entity** — Entity's state has `restored: true`, meaning HA
  loaded its last value from the recorder because the integration is no
  longer providing it. Most common after removing an integration without
  cleaning up its entities. The `platform` field tells you which
  integration *used* to own it.
- **Unavailable entity** *(HAGHS-parity)* — A *single* entity in
  `unavailable` or `unknown` state for more than **15 minutes** on an
  otherwise-healthy device. Catches the cases the device-level checks
  miss: e.g. an iPhone Companion App where Focus / Steps / Distance /
  Floors are individually broken even though the parent device is
  online and other sensors report fine. The detection is restricted
  to "real signal" domains (`sensor`, `binary_sensor`, `switch`,
  `light`, `fan`, `climate`, `media_player`, `vacuum`, `camera`) so
  that buttons / events / scenes don't generate false positives.
  Sorted stalest-first in the table (longest `unavailable_for_seconds`
  on top — most likely to be true zombies).

### Grace period and ignore-label

- **15-minute grace window** is hard-coded (matches HAGHS). An entity
  must have been `unavailable`/`unknown` for that long before the
  `unavailable_entity` bucket flags it. This tolerates HA restarts and
  brief integration reloads.
- **Ignore label**: `haghs_ignore` by default (override via
  `--ignore-label LABEL` or env `HACTL_IGNORE_LABEL`). Any entity OR its
  parent device that carries the label in its registry `labels` list is
  skipped from EVERY zombie category. This gives you a per-record opt-
  out without code changes — and it's cross-tool compatible with HAGHS.

## Triage workflow

The canonical 4-step flow:

**1. Dump everything to disk:**

```bash
mise exec -- hactl get zombie-devices -o json > /tmp/zombies.json
```

**2. Group first. Don't tackle one device at a time.** Cluster by
`via_device_id` (parent hub) and `integration` — this turns 230
individual records into a handful of decisions:

```bash
# Orphans, grouped by parent hub and integration
jq '[.[] | select(.category=="orphan")]
    | group_by(.via_device_id)
    | map({parent: .[0].via_device_id, count: length, integrations: (map(.integration) | unique)})
    | sort_by(-.count)' /tmp/zombies.json

# Restored entities, grouped by integration
jq '[.[] | select(.category=="restored_entity")]
    | group_by(.integration)
    | map({integration: .[0].integration, count: length})
    | sort_by(-.count)' /tmp/zombies.json
```

**3. For each cluster, decide:**

| Pattern | Action |
|---------|--------|
| All orphans share one `via_device_id` | Remove the parent device first; children disappear with it. |
| All restored entities share one `integration` | The integration was removed. Either re-add it, or delete the entities (Developer Tools → States → trash icon) — they'll be purged after 10 days otherwise. |
| Stalled with `last_seen` >30 days | Battery dead or device unplugged. If it's not coming back, delete. |
| Disabled with `disabled_by: user` | You disabled it on purpose. Leave it. |
| Disabled with `disabled_by: config_entry` | The integration disabled it (e.g. Flic when the hub is offline). Re-enable the integration to re-enable the device, or delete if you've moved on. |

To delete a device in the HA UI: **Settings → Devices & Services →
Devices → click the device → trash icon (top right)**.

For a restored entity that's *not* device-bound: **Developer Tools →
States → click the entity → red trash icon**. Or wait — HA purges
restored entities after 10 days.

**Or pipe straight into `hactl delete`** (kubectl-style, dry-run by
default):

```bash
# Manual review of the plan first.
hactl get zombie-devices -o json --category orphan \
  | hactl delete -f - --dry-run

# Commit (audit log written automatically).
hactl get zombie-devices -o json --category orphan \
  | hactl delete -f - --yes --limit 200
```

### Recommended pattern for `unavailable_entity` cleanup

Because `unavailable_entity` records are *individual* entities (not
devices), the safe sequence is:

```bash
# 1. Inspect grouped by integration so you can see the cluster shape.
hactl get zombie-devices -o json --category unavailable_entity \
  | jq 'group_by(.integration)
        | map({integration: .[0].integration, count: length})
        | sort_by(-.count)'

# 2. Use --state-only unavailable on `hactl delete entities` so live
#    entities are filtered out BEFORE the safety predicate ever sees
#    them. This is the recommended safe pattern.
hactl delete entities --filter platform=mobile_app \
                      --state-only unavailable --dry-run

# 3. Commit.
hactl delete entities --filter platform=mobile_app \
                      --state-only unavailable --yes --limit 200
```

Never run `hactl delete entities --filter platform=X` *without*
`--state-only unavailable` unless you've manually verified every match.
The pattern alone will catch any working sensor on the same platform.
The bulk-form safety predicate hard-refuses live-state entities without
`--force` — see [`docs/delete.md`](delete.md).

See [`docs/delete.md`](delete.md) for the full deletion SOP, the
safety predicate, and the audit-log shape.

**4. Re-scan and confirm:**

```bash
mise exec -- hactl doctor --check zombie_devices
```

The summary count should drop. Anything left over is either
intentional (disabled, stable) or part of the next cluster.

## Common patterns (concrete examples)

- *"All 5 Shellies are orphans, similar MAC addresses"* — A device was
  renamed or re-paired to the same hub. Old registry entries are
  stranded. Safe to delete all five; they'll come back if the device
  is genuinely still on-network.
- *"53 `device_tracker.*` restored entities, all `platform: mobile_app`"*
  — Mobile app integration was removed but entities lingered. Delete
  via Developer Tools → States, or wait 10 days for the recorder
  purge.
- *"Stalled Aqara temp sensor, `last_seen` 47 days ago"* — Battery
  dead. Replace the battery (the device should re-appear) or remove
  it from Zigbee2MQTT/ZHA, then delete the HA device.
- *"13 disabled Flic buttons, all `disabled_by: config_entry`"* —
  Flic Hub integration is in `setup_retry`. Fix the integration
  (`hactl doctor --check config_entries`) and the buttons re-enable
  themselves. Don't delete unless you're done with Flic.

## What this command WON'T do

- It will **not** delete or modify any device, entity, integration, or
  state. Strictly read-only — `hactl delete` is the destructive sibling
  (see [`docs/delete.md`](delete.md)).
- It does **not** detect ZHA-internal "stale" devices that show up only
  in the ZHA panel — those need ZHA's own UI.

## See also

- `hactl doctor --check zombie_devices` — short summary (counts +
  top-5 per category). Use this for the daily / scheduled scan.
- `hactl get devices` — the full live device registry.
- `hactl doctor --check config_entries` — the place to investigate
  `disabled_by: config_entry` clusters before deleting anything.
