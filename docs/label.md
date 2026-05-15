# `hactl label`

Generic, kubectl-style management of Home Assistant **labels** on
devices and entities. Mirrors the verb/resource shape of `hactl get`
and `hactl delete`.

The driving use case: HA's label registry is the standard mechanism
for telling other tools (HAGHS, `hactl get zombie-devices`,
`hactl doctor`) "this device is known-flaky, stop counting it as a
problem." Labelling devices manually through the UI is slow and
unreproducible. `hactl label` gives you a CLI-native, idempotent
workflow plus an `--from-allowlist` mode that ingests the cberg
homelab's `noise_allowlist.yaml` shape directly.

## Synopsis

```
hactl label list                       [-o table|json]

hactl label apply  --device <id|name>     --label <id> [common opts]
hactl label apply  --entity <entity_id>   --label <id> [common opts]
hactl label apply  --from-allowlist <YAML> --label <id> [common opts]

hactl label remove --device <id|name>     --label <id> [common opts]
hactl label remove --entity <entity_id>   --label <id> [common opts]
hactl label remove --from-allowlist <YAML> --label <id> [common opts]
```

`--device`, `--entity`, and `--from-allowlist` are repeatable /
combinable. The plan is the union of every resolved target.

### Common options (apply / remove)

| Flag | Default | Meaning |
|------|---------|---------|
| `--dry-run`  | off (but on by default unless `--yes`) | Force dry-run, no API calls. |
| `--yes`      | off | Commit. Without this, runs as dry-run. |
| `--limit N`  | 200 | Max **changing** records per batch (no-ops don't count). |
| `--audit PATH` | `/tmp/hactl-label-<ts>.json` | Audit log path (only written on real run). |
| `--quiet`    | off | Suppress per-record progress output. |

## Hard rules

1. **Default is dry-run.** Without `--yes`, every invocation prints the
   planned label diff and exits without touching HA.
2. **Read-modify-write.** HA's `*_registry/update` REPLACES the labels
   list — `hactl label` always reads the current labels first, computes
   the new sorted set, and writes only when the set actually changed.
   This is what makes the command idempotent.
3. **Auto-creates the target label.** If the label_id you pass to
   `apply` doesn't exist in `config/label_registry/list`, the run
   creates it (`config/label_registry/create`) before the first device
   update. Re-runs that find the label already present skip the
   create. `remove` never creates labels.
4. **Audit log on every real run.** When the run mutates HA (label
   create or any registry update), a JSON audit log is written
   capturing: timestamp, hactl version, user, host, invocation,
   per-record `pre_labels` / `post_labels` / `result`, and any
   label_creations.
5. **Limit gate.** `--limit` blocks runs that would change more than N
   records at once. Only **changing** records count — a 500-target run
   where 499 are already labelled will not trip a `--limit 200` gate.

## `hactl label list`

Print every label in the registry plus per-label device + entity usage
counts. Labels that are in use on a record but missing from the
registry surface as `(unregistered)` — usually a sign of an HA UI bug
or a manual import.

```bash
hactl label list
hactl label list -o json
```

Sample output:

```
=== Labels (3) ===
LABEL_ID                  DEVICES  ENTITIES  NAME
----------------------------------------------------------------------
haghs_ignore                   12         0  haghs_ignore
keepme                          0         3  keepme
existing_label                  1         0  existing_label
```

## `hactl label apply`

Add a label to one or more devices and/or entities. The label is
auto-created if it doesn't exist.

### Single device

```bash
# By id
hactl label apply --device d7a19fa12e12ce6b8be1936995822273 \
                  --label haghs_ignore --yes

# By name (matches name_by_user OR name, case-insensitive)
hactl label apply --device "Soil sensor 3" --label haghs_ignore --yes
```

### Single entity

```bash
hactl label apply --entity sensor.living_room_temp \
                  --label haghs_ignore --yes
```

### From a noise allowlist (YAML)

This is the cberg homelab use case: the daily HAGHS / sweep agent
keeps a `noise_allowlist.yaml` of known-flaky devices that should not
count as problems. Feeding that file to `hactl label apply` makes the
HA registry agree, so HAGHS / `hactl get zombie-devices` / `hactl
doctor` will all skip those devices automatically.

```bash
hactl label apply \
  --from-allowlist /path/to/noise_allowlist.yaml \
  --label haghs_ignore \
  --dry-run

# Review the plan, then commit:
hactl label apply \
  --from-allowlist /path/to/noise_allowlist.yaml \
  --label haghs_ignore \
  --yes
```

#### Allowlist YAML schema

`hactl label` reads two top-level lists:

```yaml
flaky_zigbee_devices:
  - "Soil sensor 3"                       # bare string = device name
  - name: "Some other Zigbee device"      # object form
    note: "optional, ignored by hactl"

flaky_iot_devices:
  - name: "Shelly Entry Window Blinds"
    note: "WiFi flap; ignored by hactl"
```

Other sections (`recurring_alerts`, `unexpected_jobs`,
`known_services_without_endpoints`, etc.) are ignored — `hactl label`
only consumes the two device lists.

#### Match strategy

For each name in the allowlist:

1. **Exact case-insensitive match** against `device.name_by_user`
   THEN `device.name`.
2. **Case-insensitive substring fallback** against the same fields.
   When this fires, the run prints a `Fuzzy matches:` block so the
   operator can sanity-check before passing `--yes`.
3. **No match** → the name is reported under `Unmatched allowlist
   entries:` and the run continues. Unmatched names never block the
   batch.

## `hactl label remove`

The inverse of `apply`. Same flag set, same dry-run semantics, never
creates labels.

```bash
hactl label remove --device "Soil sensor 3" --label haghs_ignore --yes
hactl label remove --entity sensor.foo      --label haghs_ignore --yes
```

## Idempotency

Re-running the exact same `apply` (or `remove`) is safe and costs
nothing on the wire:

- If the target label already exists in the registry → no
  `label_registry/create` call.
- If a target device/entity already has the desired label set →
  no `*_registry/update` call.
- If neither the label nor any record needs changing → the run
  short-circuits before opening a WebSocket.

The output for a fully no-op run says `No changes required (idempotent).`
and exits 0 with no audit log written.

## Audit log

When a real run mutates HA, an audit JSON like this is written:

```json
{
  "timestamp": "2026-05-13T12:34:56+00:00",
  "hactl_version": "...",
  "user": "...",
  "host": "...",
  "platform": "...",
  "invocation": ["hactl", "label", "apply", "--from-allowlist", "...", "..."],
  "label_creations": [
    {"label_id": "haghs_ignore", "op": "created"}
  ],
  "records": [
    {
      "kind": "device",
      "id": "d7a19fa12e12ce6b8be1936995822273",
      "op": "add",
      "label": "haghs_ignore",
      "pre_labels": [],
      "post_labels": ["haghs_ignore"],
      "changed": true,
      "result": "updated",
      "error": null,
      "pre_state": {"name": "Yard Soil Sensor Roses",
                    "id": "d7a19fa12e12ce6b8be1936995822273"}
    }
  ]
}
```

`pre_labels` and `post_labels` are sorted sets so audit-log diffs
across runs are stable.

## Cross-tool integration

- **`hactl get zombie-devices --ignore-label haghs_ignore`** — every
  category (orphans, stalled, disabled, restored, unavailable_entities)
  skips records that themselves OR whose parent device carry
  `haghs_ignore`.
- **`hactl doctor`** — same logic, same default label.
- **HAGHS** — `haghs_ignore` is the cross-tool convention. Labels
  applied by `hactl label apply` show up in HAGHS' registry pull
  immediately.

## Common workflows

### Suppress known-flaky-devices noise (cberg pattern)

```bash
# 1. Dry-run against the homelab allowlist, review the plan
mise exec -- hactl label apply \
  --from-allowlist /Users/mu/code/cberg-home-nextgen/runbooks/noise_allowlist.yaml \
  --label haghs_ignore --dry-run

# 2. Commit
mise exec -- hactl label apply \
  --from-allowlist /Users/mu/code/cberg-home-nextgen/runbooks/noise_allowlist.yaml \
  --label haghs_ignore --yes

# 3. Verify the label is now in use
mise exec -- hactl label list

# 4. Confirm the daily zombie count drops
mise exec -- hactl get zombie-devices
```

### One-off: hide a specific device from zombie scans

```bash
mise exec -- hactl label apply \
  --device "Living Room Lamp" --label haghs_ignore --yes
```

### Periodic re-sync

`hactl label apply --from-allowlist ... --label haghs_ignore --yes`
is safe to run on a schedule — it's fully idempotent. Use it whenever
the allowlist changes.

## Troubleshooting

**"WebSocket fetch failed"** — the WS API didn't answer. Check `.env`
URL/token and try `hactl get devices`.

**"Unmatched allowlist entries"** — a name in the YAML doesn't match
any device in HA. Either rename in the allowlist, rename the device
in HA (`name_by_user`), or drop the entry. The run continues with the
matched names.

**"Fuzzy matches"** warning — the entry only matched as a substring,
not exactly. Verify the matched device is what you intended before
passing `--yes`.

**Old HA without label_registry** — `hactl label list` will report 0
labels and `apply` will fail at the create step. Upgrade HA.
