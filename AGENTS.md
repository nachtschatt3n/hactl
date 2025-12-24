# hactl - AI Assistant Guide

## What is hactl?

**hactl** is a kubectl-style command-line interface for managing Home Assistant. It's designed to be used BY AI assistants (like Claude, ChatGPT, etc.) to efficiently manage Home Assistant installations without requiring massive token usage.

## Why hactl Exists

When helping users with Home Assistant, AI assistants typically need to:
1. Query current device states (2000+ entities = huge JSON response)
2. Understand the home layout and device relationships
3. Create or modify dashboards and automations
4. Check battery levels across many devices

**The Problem:** Querying all states repeatedly uses tens of thousands of tokens and is slow.

**The Solution:** hactl's memory system stores compact CSV snapshots of the entire Home Assistant state, allowing AI assistants to understand the full setup in just a few thousand tokens.

## Core Concept: Memory System

### How It Works

1. **User runs once:** `hactl memory sync`
2. **Creates CSV files:**
   - `memory/devices.csv` - All devices with manufacturer, model, area
   - `memory/states.csv` - All entities with current values
   - `memory/automations.csv` - All automations with status
   - `memory/dashboards.csv` - All dashboards
   - `memory/hacs.csv` - Installed HACS repositories
   - `memory/areas.csv` - All areas/rooms with aliases
   - `memory/integrations.csv` - All configured integrations
   - `memory/scripts.csv` - All scripts with last triggered time
   - `memory/scenes.csv` - All scenes with icons
   - `memory/templates.csv` - Template sensors with formulas
   - `memory/entity_relationships.csv` - Entity relationships and groupings
   - `memory/automation_stats.csv` - Automation statistics and history
   - `memory/service_capabilities.csv` - Available service domains
   - `memory/battery_health.csv` - Battery sensor health tracking
   - `memory/energy_data.csv` - Energy and power sensors for optimization
   - `memory/automation_context.csv` - User annotations about automation purposes (editable)
   - `memory/persons_presence.csv` - Household members, device trackers, and occupancy sensors

3. **AI reads CSV files** instead of querying live API repeatedly
4. **Token savings:** 90% reduction vs JSON API responses

**Note:** The examples below use placeholder data. Run `hactl memory sync` and check your own memory/ directory for actual device names and counts.

### When to Use Memory

✅ **Use memory files when:**
- Understanding the overall home setup
- Finding what devices/sensors exist
- Planning dashboards or automations
- Need context about the home layout

❌ **Query live when:**
- Need real-time current state
- Checking if automation just triggered
- Verifying a change was applied

### Example Workflow

```bash
# First time: Sync HA state to memory
hactl memory sync

# AI reads memory/states.csv to understand all entities
# AI reads memory/devices.csv to understand device relationships

# AI uses this context to help user create automations
# without needing to query everything repeatedly
```

## Command Groups Overview

### GET - Read Resources (29 commands)

Read current state from Home Assistant:

```bash
# Most commonly used
hactl get devices                    # All devices (use memory/devices.csv for bulk)
hactl get states                     # All entity states (use memory/states.csv for bulk)
hactl get states --domain light      # Just lights
hactl get sensors battery            # Battery sensors
hactl get automations                # All automations
hactl get dashboards                 # All dashboards

# Useful for specific queries
hactl get services                   # Available services
hactl get integrations               # Configured integrations
hactl get history                    # Recent activity
hactl get events                     # Event stream
```

**Output formats:**
- `--format table` (default, human-readable)
- `--format json` (for parsing)
- `--format yaml` (for configs)
- `--format csv` (compact)

**Special dashboard features:**
```bash
# Get specific view from dashboard
hactl get dashboards --format yaml-single --url-path dashboard/view

# Validate entities against current HA state
hactl get dashboards --format validate --url-path dashboard/view
# → Reports missing entities with suggestions
```

### UPDATE - Modify Resources (2 commands)

Update Home Assistant configurations:

```bash
# Update or create dashboard
hactl update dashboard my-dashboard --from dashboard.yaml

# Update helper configuration
hactl update helper battery-summary.yaml
```

### BATTERY - Monitoring (3 commands)

Battery management utilities:

```bash
# List all battery devices
hactl battery list
hactl battery list --exclude-mobile

# Check battery summary sensors
hactl battery check

# Create battery monitoring setup
hactl battery monitor
```

### K8S - Kubernetes Operations (4 commands)

For Kubernetes-deployed Home Assistant:

```bash
# Find Home Assistant pod
hactl k8s find-pod --namespace home-automation

# Download configuration from pod
hactl k8s get-config --output config.yaml
hactl k8s get-config --file /config/templates.yaml --output templates.yaml

# Upload configuration to pod (automatically creates backup and restarts)
hactl k8s put-config config.yaml
hactl k8s put-config config.yaml --no-restart  # Skip restart
hactl k8s put-config config.yaml --no-backup   # Skip backup (not recommended)

# Update config with helper sensors (automated merge)
hactl k8s update-config helper.yaml --namespace home-automation
hactl k8s update-config helper.yaml --dry-run  # Preview changes
```

**Important Notes:**
- `put-config` automatically creates timestamped backups before updating
- `put-config` automatically restarts Home Assistant after upload (use --no-restart to skip)
- `update-config` merges template sensors into configuration.yaml
- Always use `--dry-run` first to preview changes

### MEMORY - AI Context Management (5 commands)

**Most important commands for AI assistants:**

```bash
# Sync current HA state to CSV files
hactl memory sync

# List all memory files
hactl memory list

# Add contextual notes
hactl memory add sensor bedroom_temp "Reads 2°C high, needs calibration"

# Show notes for category
hactl memory show sensors

# Edit memory files directly
hactl memory edit context/preferences.md
```

## Best Practices for AI Assistants

### 1. Start with Memory Sync

When first helping a user, suggest:

```bash
hactl memory sync
```

Then read the CSV files to understand their setup instead of querying live.

### 2. Use Appropriate Commands

**For discovery/planning:**
- Read `memory/states.csv`
- Read `memory/devices.csv`
- Use `hactl get --format json` for specific queries

**For real-time checks:**
- Use `hactl get states --domain light` for current light states
- Use `hactl get history` for recent activity

**For modifications:**
- Use `hactl update dashboard` to create/modify dashboards
- Use YAML format for configs

### 3. Output Format Selection

```bash
# Parsing in scripts → use json
hactl get sensors battery --format json | jq '.[0]'

# Creating configs → use yaml
hactl get dashboards --format yaml

# Human review → use table (default)
hactl battery list

# Token-efficient → use csv or read memory files
```

### 4. Error Handling

All commands return appropriate exit codes:
- `0` = success
- `1` = error (with message on stderr)
- `2` = usage error

Check exit codes and handle errors appropriately.

### 5. Testing Requirement

**CRITICAL:** All new features and commands MUST be tested in `test_hactl_commands.sh`

```bash
# Run tests before suggesting changes
./test_hactl_commands.sh

# Tests include:
# - 32 import validation tests
# - 42 command tests
# - Output format tests
# - Error handling tests
```

## Common AI Tasks

### Task: Help user create automation

```bash
# 1. Read memory to understand devices
cat memory/states.csv | grep automation
cat memory/devices.csv

# 2. Get specific device details
hactl get states --domain light --format json

# 3. Create automation YAML
# (AI generates YAML based on understanding)

# 4. Test automation
# (User applies via Home Assistant UI)
```

### Task: Create dashboard for battery monitoring

```bash
# 1. Get battery devices
hactl battery list --format json

# 2. Generate dashboard YAML
# (AI creates lovelace YAML)

# 3. Apply dashboard
hactl update dashboard battery-monitor --from dashboard.yaml
```

### Task: Check dashboard for errors

**IMPORTANT:** Understand HA dashboard structure first!

```bash
# 1. ALWAYS start with memory sync
hactl memory sync

# 2. List all dashboards to understand structure
hactl get dashboards --format json

# 3. Get specific view directly (NEW FEATURE!)
# hactl now supports dashboard/view paths:
hactl get dashboards --format yaml-single --url-path light-control/battery-monitor

# 4. Cross-reference entities with memory/states.csv
cat memory/states.csv | grep battery

# 5. Find missing entities by comparing view YAML with states.csv
```

**What's new:**
- ✅ Can now use view paths directly: `dashboard-name/view-name`
- ✅ hactl automatically extracts just that view
- ✅ Much more intuitive than getting full dashboard and parsing manually

**Common mistakes to avoid:**
- ❌ Don't explore endlessly without syncing memory first
- ❌ Don't parse JSON output in complex ways when CSV is simpler
- ✅ Use memory files to quickly verify entity existence
- ✅ Use view paths directly: `hactl get dashboards --url-path dashboard/view`

### Task: Troubleshoot automation

```bash
# 1. Check automation status
hactl get automations --format detail

# 2. Check recent history
hactl get history

# 3. Check entity states
hactl get states --domain sensor --format json
```

## Memory File Structure

After `hactl memory sync`, these files are created:

```
memory/
├── devices.csv                  # device_id,name,manufacturer,model,area_id,sw_version
├── states.csv                   # entity_id,domain,friendly_name,state,device_class,unit,area_id
├── automations.csv              # entity_id,friendly_name,state,last_triggered
├── dashboards.csv               # url_path,title,icon
├── hacs.csv                     # name,category,version,authors,description,full_name
├── areas.csv                    # area_id,name,aliases
├── integrations.csv             # domain,title,state,source
├── scripts.csv                  # entity_id,friendly_name,last_triggered
├── scenes.csv                   # entity_id,friendly_name,icon
├── templates.csv                # entity_id,friendly_name,unit,device_class,state_class
├── entity_relationships.csv     # entity_id,related_entity,relationship_type,context
├── automation_stats.csv         # entity_id,friendly_name,state,last_triggered,mode,currently_running
├── service_capabilities.csv     # domain,service,description,parameters,required_params
├── battery_health.csv           # entity_id,friendly_name,current_level,level_numeric,unit,device_class
├── energy_data.csv              # entity_id,friendly_name,category,current_value,value_numeric,unit,device_class,state_class
├── automation_context.csv       # entity_id,friendly_name,purpose,category,user_notes (editable)
├── persons_presence.csv         # entity_id,type,friendly_name,state,location,latitude,longitude,source,device_class
└── context/                     # User-created context (gitignored)
    ├── preferences.md           # User preferences
    └── notes.md                 # Custom notes
```

### Memory File Examples

Each memory file contains specific data from your Home Assistant installation. Below are example CSV structures:

#### devices.csv
```csv
device_id,name,manufacturer,model,area_id,sw_version
abc123...,Kitchen Light,Philips,Hue White,kitchen,1.2.3
def456...,Bedroom Sensor,Aqara,Temperature Sensor,bedroom,2.1.0
```

#### states.csv
```csv
entity_id,domain,friendly_name,state,device_class,unit,area_id
light.kitchen,light,Kitchen Light,on,,,kitchen
sensor.bedroom_temp,sensor,Bedroom Temperature,22.5,temperature,°C,bedroom
sensor.motion_battery,sensor,Motion Sensor Battery,85,battery,%,living_room
```

#### automations.csv
```csv
entity_id,friendly_name,state,last_triggered
automation.morning_routine,Morning Routine,on,2025-01-15T06:30:00Z
automation.night_lights,Night Lights,on,2025-01-15T22:00:00Z
```

#### dashboards.csv
```csv
url_path,title,icon
home,Home,mdi:home
lights,Light Control,mdi:lightbulb
energy,Energy Monitor,mdi:flash
```

#### hacs.csv
```csv
name,category,version,authors,description,full_name
Custom Integration,integration,1.0.0,developer,Description here,user/repo
Theme Name,theme,2.1.0,designer,Custom theme,user/theme-repo
```

#### areas.csv
```csv
area_id,name,aliases
kitchen,Kitchen,"Cook Room"
bedroom,Bedroom,"Master Bedroom, BR"
living_room,Living Room,"Lounge, LR"
```

#### integrations.csv
```csv
domain,title,state,source
mqtt,MQTT Broker,loaded,user
hacs,HACS,loaded,user
esphome,ESPHome Device,loaded,user
```

#### scripts.csv
```csv
entity_id,friendly_name,last_triggered
script.bedtime_routine,Bedtime Routine,2025-01-15T22:00:00Z
script.movie_mode,Movie Mode,2025-01-14T19:30:00Z
```

#### scenes.csv
```csv
entity_id,friendly_name,icon
scene.bright,Bright,mdi:brightness-7
scene.dimmed,Dimmed,mdi:brightness-5
scene.evening,Evening,mdi:weather-sunset
```

#### templates.csv
```csv
entity_id,friendly_name,unit,device_class,state_class
sensor.room_heater_temperature,Room Heater Temperature,°C,temperature,measurement
sensor.plug_power,Smart Plug Power,W,power,measurement
sensor.plug_energy,Smart Plug Energy,kWh,energy,total_increasing
```

#### entity_relationships.csv
```csv
entity_id,related_entity,relationship_type,context
light.bedroom_main,sensor.bedroom_motion,same_area,bedroom
climate.living_room,sensor.living_room_temp,same_area,living_room
```

#### automation_stats.csv
```csv
entity_id,friendly_name,state,last_triggered,mode,currently_running
automation.morning_routine,Morning Routine,on,2025-01-15T06:30:00Z,single,0
automation.motion_lights,Motion Lights,on,2025-01-15T14:22:00Z,restart,0
```

#### service_capabilities.csv
```csv
domain,service,description,parameters,required_params
light,unknown,,,
climate,unknown,,,
automation,unknown,,,
```
*Note: Currently captures service domains. Full service details (individual services and parameters) may require additional API endpoints.*

#### battery_health.csv
```csv
entity_id,friendly_name,current_level,level_numeric,unit,device_class
binary_sensor.door_lock_battery,Door Lock Battery,off,,,battery
sensor.motion_sensor_battery,Motion Sensor Battery,85,85,%,battery
sensor.window_sensor_battery,Window Sensor Battery,100,100,%,battery
```

#### energy_data.csv
```csv
entity_id,friendly_name,category,current_value,value_numeric,unit,device_class,state_class
sensor.solar_power,Solar Power,solar_production,1500,1500.0,W,power,measurement
sensor.solar_energy_total,Solar Energy Total,solar_production,125.5,125.5,kWh,energy,total
sensor.server_power,Server Power,power_usage,45.2,45.2,W,power,measurement
sensor.server_energy,Server Energy,energy_consumption,12.8,12.8,kWh,energy,total_increasing
sensor.grid_voltage,Grid Voltage,electrical_monitoring,230.0,230.0,V,voltage,measurement
```
*Categories vary by installation: solar_production, energy_consumption, power_usage, electrical_monitoring*

#### automation_context.csv (editable)
```csv
entity_id,friendly_name,purpose,category,user_notes
automation.morning_routine,Morning Routine,wake_up,comfort,Gradual lights at 6:30am
automation.bedtime,Bedtime,energy_saving,efficiency,Turn off all lights at 11pm
```
*Note: Users can edit this file to add purpose, category, and notes. Context is preserved across syncs.*

#### persons_presence.csv
```csv
entity_id,type,friendly_name,state,location,latitude,longitude,source,device_class
person.john_doe,person,John Doe,home,,50.123,8.456,device_tracker.johns_phone,
person.jane_doe,person,Jane Doe,not_home,,48.789,9.012,device_tracker.janes_phone,
device_tracker.johns_phone,device_tracker,John's Phone,home,,50.123,8.456,gps,
device_tracker.janes_tablet,device_tracker,Jane's Tablet,not_home,,48.789,9.012,gps,
device_tracker.living_room_tv,device_tracker,Living Room TV,home,,,,router,
binary_sensor.living_room_occupancy,occupancy_sensor,Living Room Occupancy,on,,,,,occupancy
binary_sensor.bedroom_occupancy,occupancy_sensor,Bedroom Occupancy,off,,,,,occupancy
```
*Types: person (household members), device_tracker (phones/devices), occupancy_sensor (room presence)*

### Understanding the Phase 1 Memory Additions

The three new memory files (templates, entity_relationships, automation_stats) provide **contextual understanding** beyond just current state:

**templates.csv** - Know which sensors are computed/derived:
- Helps AI distinguish between physical sensors (raw data) and template sensors (computed values)
- `state_class` tells if it's a measurement, total, or total_increasing (useful for energy tracking)
- Example: Energy sensors with `state_class=total_increasing` indicate cumulative consumption

**entity_relationships.csv** - Understand entity groupings:
- Shows which entities work together (same area, automation triggers, etc.)
- Helps AI suggest relevant automations ("motion sensor in kitchen could trigger kitchen lights")
- Area-based relationships show which entities are in the same room

**automation_stats.csv** - Track automation health:
- `last_triggered` shows if automation is actually being used
- `mode: single/restart/queued/parallel` indicates automation behavior
- `currently_running` shows if automation is stuck or long-running
- Example: If `last_triggered` is months old, automation might be broken or unnecessary

**AI Usage Tips:**

1. **Creating automations?** Check templates.csv to avoid re-computing existing values
2. **Dashboard design?** Use entity_relationships.csv to group related entities together
3. **Troubleshooting?** Check automation_stats.csv for last_triggered times and running state
4. **Energy monitoring?** Filter templates.csv for `device_class=energy` and `state_class=total_increasing`

### Understanding the Phase 2 Memory Additions

The Phase 2 additions (service_capabilities, battery_health) provide **operational awareness** for maintenance and capabilities:

**service_capabilities.csv** - Know what service domains are available:
- Helps AI know which integrations offer services
- Shows which domains can be controlled (light, climate, automation, etc.)
- Example: Seeing "light" domain means AI can suggest light control automations
- Note: Currently captures domains only; full service parameters require additional API access

**battery_health.csv** - Proactive battery monitoring:
- Tracks all battery sensors with current levels
- `level_numeric` field allows easy sorting to find low batteries
- Mix of binary (on/off) and percentage sensors
- Example: Sensors below 20% need attention soon

**AI Usage Tips:**

1. **Battery maintenance?** Sort battery_health.csv by `level_numeric` to find devices needing replacement
2. **Capability discovery?** Check service_capabilities.csv to see which domains have services
3. **Proactive alerts?** Filter battery_health.csv for `level_numeric < 20` to suggest low battery warnings
4. **Service calls?** Verify domain exists in service_capabilities.csv before suggesting automation actions

### Understanding the Phase 3 Memory Additions

The Phase 3 additions (energy_data, automation_context) provide **energy optimization** and **automation intent**:

**energy_data.csv** - Comprehensive energy monitoring:
- Automatically categorizes sensors: solar_production, energy_consumption, power_usage, electrical_monitoring
- `value_numeric` field enables easy calculations and comparisons
- Tracks solar production, device power usage, and electrical monitoring
- Example: Solar production sensors, smart plug power monitoring, voltage/current sensors

**automation_context.csv** - User-provided automation intent (editable):
- Template file for users to document automation purposes
- Fields: purpose, category, user_notes
- **Preserved across syncs** - user annotations won't be overwritten
- Example: Document "automation.bedtime → purpose: energy_saving, notes: Turn off all lights at 11pm"

**AI Usage Tips:**

1. **Energy optimization?** Filter energy_data.csv by `category='solar_production'` to find generation sensors
2. **Load shifting?** Compare `power_usage` sensors with `solar_production` to suggest optimal times
3. **Cost analysis?** Sort `energy_consumption` by `value_numeric` to find highest consumers
4. **Solar maximization?** Identify devices that could run during peak solar production hours
5. **Automation understanding?** Check automation_context.csv for user-provided purposes before suggesting changes
6. **Intent-aware suggestions?** Use automation context to avoid conflicting with user's documented goals

**Energy Optimization Examples:**

```bash
# Find all solar production sensors
grep "solar_production" memory/energy_data.csv

# Find highest power consumers (sorted by value_numeric field)
grep "power_usage" memory/energy_data.csv | sort -t',' -k5 -nr | head -10

# Identify devices for load shifting
# Look for constant power draws that could run during solar production peak
# Example: Servers, chargers, appliances with flexible schedules
```

### Understanding Persons & Presence Tracking

The **persons_presence.csv** file provides household occupancy and location awareness:

**person entities** - Household members:
- Shows current state: home, not_home, or specific zone names
- Includes GPS coordinates when available
- `source` field shows which device tracker is primary for this person

**device_tracker entities** - Devices and presence:
- GPS trackers: Phones/tablets with precise location (latitude/longitude)
- Router trackers: Network devices showing home/not_home
- Bluetooth LE trackers: Local presence detection
- Source types: gps, router, bluetooth_le, etc.

**occupancy_sensor entities** - Room-level presence:
- Binary sensors with device_class=occupancy
- Shows which rooms are currently occupied
- Useful for room-specific automations

**AI Usage Tips:**

1. **Home/Away detection?** Check person entities' state field (home/not_home)
2. **Room occupancy?** Filter for `type=occupancy_sensor` and `state=on`
3. **Who's home?** Count persons with `state=home`
4. **Presence-based automations?** Use occupancy sensors to know which rooms are in use
5. **Location-aware?** Use GPS coordinates from device_trackers for zone-based logic
6. **Device presence?** Router-based trackers show which devices are on the network

**Presence Examples:**

```bash
# Find who's home
grep "^person\." memory/persons_presence.csv | grep ",home,"

# Find active rooms
grep "occupancy_sensor" memory/persons_presence.csv | grep ",on,"

# Find GPS-tracked devices
grep "gps" memory/persons_presence.csv

# Count household members
grep "^person\." memory/persons_presence.csv | wc -l
```

### Reading Memory Files in Python

```python
import csv

# Read all devices
with open('memory/devices.csv', 'r') as f:
    reader = csv.DictReader(f)
    devices = list(reader)

# Read all states
with open('memory/states.csv', 'r') as f:
    reader = csv.DictReader(f)
    states = list(reader)

# Find all lights
lights = [s for s in states if s['domain'] == 'light']
```

### Reading Memory Files as AI

Just read the CSV as text - it's designed to be token-efficient:

```
entity_id,domain,friendly_name,state,device_class,unit,area_id
light.kitchen,light,Kitchen Light,on,,,kitchen
sensor.kitchen_temp,sensor,Kitchen Temperature,22.5,temperature,°C,kitchen
sensor.bedroom_battery,sensor,Bedroom Sensor Battery,85,battery,%,bedroom
```

## Configuration

hactl uses `.env` file for configuration:

```bash
# Required
HASS_URL="https://your-homeassistant-url.com"
HASS_TOKEN="your_long_lived_access_token_here"

# Optional (for K8s commands)
K8S_NAMESPACE="home-automation"
```

## Token Efficiency Tips

1. **Read memory files first** - `memory/states.csv` is ~100x smaller than JSON API response
2. **Use domain filtering** - `--domain light` instead of getting all states
3. **Use CSV format** - More compact than JSON
4. **Cache memory** - Don't re-sync unless state changed
5. **Batch queries** - Combine multiple `get` commands when possible

## Efficiency Anti-Patterns (What NOT to do)

Based on real AI assistant sessions, here are common mistakes that waste tokens and time:

### ❌ Anti-Pattern: Endless Exploration
```bash
# DON'T DO THIS:
ls
rg battery
rg battery-monitor
ls dashboards
ls generated
rg --files
# ... 20 more exploratory commands
```

**Instead:**
```bash
# DO THIS:
hactl memory sync                           # Sync once
cat memory/states.csv | grep battery       # Verify entities exist
hactl get dashboards --format json         # Get structure
```

### ❌ Anti-Pattern: Complex JSON Parsing
```bash
# DON'T DO THIS:
hactl get dashboards --format json | python -c "import json; ..."
# (fails with timeout/pipe issues)
```

**Instead:**
```bash
# DO THIS:
hactl get dashboards --format yaml-single --url-path light-control
# or just read the CSV files
cat memory/states.csv
```

### ❌ Anti-Pattern: Wrong Command Arguments (FIXED!)
```bash
# OLD WAY (no longer needed):
hactl get dashboards --format json          # Get all dashboards
# Find parent dashboard, then extract view manually
hactl get dashboards --yaml-single --url-path light-control | grep -A 100 battery-monitor
```

**Instead:**
```bash
# NEW WAY (much better!):
hactl get dashboards --url-path light-control/battery-monitor
# hactl now understands view paths!
```

### ❌ Anti-Pattern: Not Using Memory Files
```bash
# DON'T DO THIS:
hactl get states --format json | grep sensor.battery
hactl get devices --format json | grep battery
# Querying live repeatedly
```

**Instead:**
```bash
# DO THIS:
hactl memory sync                    # Once at start
grep battery memory/states.csv      # Fast, token-efficient
grep battery memory/devices.csv     # No API calls needed
```

### ✅ Efficient Workflow Example

**Bad approach (12 minutes, many commands):**
1. Try to get battery-monitor as standalone dashboard → fails
2. Explore file system → nothing
3. Try different commands → timeout issues
4. Parse complex JSON → pipe failures
5. Eventually sync memory → should have been step 1
6. Finally find the issue

**Good approach (1 minute, 3 commands):**
1. `hactl memory sync` → Get full state
2. `hactl get dashboards --url-path light-control/battery-monitor` → Get specific view
3. `grep battery memory/states.csv` → Verify entities exist
4. Compare and identify missing entities

**Time saved:** 11 minutes, **Tokens saved:** 90%

**Even better with new features:**
```bash
# Get specific view directly:
hactl get dashboards --format yaml-single --url-path dashboard/view > view.yaml

# Validate entities automatically (no manual parsing needed!):
hactl get dashboards --format validate --url-path light-control/battery-monitor

# Output example:
# === Validating: Battery Monitor (light-control/battery-monitor) ===
# Total entities: 70
# ✓ Valid: 67
# ✗ Missing: 3
#
# Missing entities:
#   - sensor.yard_soil_sensor_2_battery
#     Suggestions:
#       → sensor.0xa4c138101f51cc54_battery (Yard Soil Sensor 2)
```

## Example: Full AI Workflow

```bash
# User: "Help me set up battery monitoring"

# 1. Sync state to memory
hactl memory sync

# 2. Read memory to understand setup (AI reads CSV files)
# AI now knows all devices, entities, and relationships

# 3. Get battery-specific devices
hactl battery list --format json

# 4. Create monitoring dashboard
# AI generates dashboard YAML from template

# 5. Apply dashboard
hactl update dashboard battery-monitor --from dashboard.yaml --create

# 6. Verify
hactl get dashboards

# Total tokens: ~5K instead of 50K+ without memory
```

## Important Reminders

1. **hactl is a tool FOR AI, not BY AI** - Don't try to make it "smart", keep it as a simple, efficient CLI
2. **Memory is optional but recommended** - Massive token savings for AI assistants
3. **All features must be tested** - Add tests to `test_hactl_commands.sh`
4. **CSV format is intentional** - More token-efficient than JSON for AI reading
5. **Memory directory is gitignored** - Contains user's private HA setup

## Security Notes

- `.env` is gitignored - never commit tokens
- Memory files are gitignored - never commit user's HA state
- Pre-commit hooks prevent accidental secret commits
- Always use environment variables, never hardcode credentials

## Development Workflow

When adding new features:

1. Implement command in `hactl/commands/`
2. Implement handler in `hactl/handlers/`
3. Add tests to `test_hactl_commands.sh`
4. Run tests: `./test_hactl_commands.sh`
5. Update README.md with new command
6. Update this CLAUDE.md if AI behavior should change

## Project Structure

```
hactl/
├── cli.py                 # Main Click entry point
├── core/                  # Core utilities
│   ├── config.py         # Environment-based config
│   ├── api.py            # REST API client
│   ├── websocket.py      # WebSocket client
│   └── formatting.py     # Output formatting
├── commands/             # Command groups (5 files)
│   ├── get.py           # GET commands (29 subcommands)
│   ├── update.py        # UPDATE commands
│   ├── battery.py       # BATTERY commands
│   ├── k8s.py           # K8S commands
│   └── memory.py        # MEMORY commands
└── handlers/            # Business logic (32 files)
    ├── devices.py
    ├── states.py
    ├── memory_mgmt.py   # Memory system (CSV generation)
    └── ...

memory/                  # gitignored, CSV files for AI context
├── devices.csv
├── states.csv
├── automations.csv
├── dashboards.csv
├── hacs.csv
├── areas.csv
├── integrations.csv
├── scripts.csv
├── scenes.csv
├── templates.csv
├── entity_relationships.csv
├── automation_stats.csv
├── service_capabilities.csv
├── battery_health.csv
├── energy_data.csv
├── automation_context.csv
└── persons_presence.csv

test_hactl_commands.sh   # Integration tests (81 tests)
```

## Summary

**hactl is your efficient interface to Home Assistant.** Use it to:
- Understand the user's setup via memory files (token-efficient)
- Query live state when needed
- Create and modify dashboards/automations
- Monitor battery levels
- Manage Kubernetes deployments

**Key principle:** Read memory first, query live second, always test changes.
