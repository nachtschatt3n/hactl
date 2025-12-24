# Changelog

All notable changes to hactl will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-24

### 🎉 Initial Release

A powerful kubectl-style CLI for managing Home Assistant via API with comprehensive memory system for AI assistants.

### Features

#### Core Commands
- **GET Commands** (29 commands) - Retrieve resources from Home Assistant
  - Devices, states, sensors, integrations, services
  - Automations, scripts, scenes, helpers, dashboards
  - Calendars, cameras, media players, persons/zones
  - Home structure, events, history, activity
  - Templates, todos, notifications, HACS
  - Energy monitoring, error logs, assist, actions

- **UPDATE Commands** (2 commands) - Modify resources
  - Update dashboards from YAML files
  - Update helper configurations

- **BATTERY Commands** (3 commands) - Battery monitoring utilities
  - List all battery-powered devices
  - Check battery summary sensors
  - Create battery monitoring setup

- **K8S Commands** (4 commands) - Kubernetes integration
  - Find Home Assistant pod
  - Download/upload configuration files
  - Update config with automated merges and restarts

- **MEMORY Commands** (5 commands) - AI context management
  - Sync current HA state to CSV files (token-efficient)
  - Add contextual notes about entities
  - Show memory for categories
  - List all memory files
  - Edit memory files directly

#### Memory System (AI Context Management)

**17 CSV Files for Token-Efficient AI Context:**

**Base System (9 files):**
- `devices.csv` - All devices with manufacturer, model, area
- `states.csv` - All entity states with current values
- `automations.csv` - All automations with status
- `dashboards.csv` - All dashboards with titles
- `hacs.csv` - Installed HACS repositories with versions
- `areas.csv` - All areas (rooms/zones) with names and aliases
- `integrations.csv` - All configured integrations with state
- `scripts.csv` - All scripts with last triggered time
- `scenes.csv` - All scenes with icons

**Advanced Features - Phase 1 (3 files):**
- `templates.csv` - Template sensors with formulas and state classes
- `entity_relationships.csv` - Area-based entity relationships (352 relationships)
- `automation_stats.csv` - Automation execution statistics

**Advanced Features - Phase 2 (2 files):**
- `service_capabilities.csv` - Available service domains and parameters (86 services)
- `battery_health.csv` - Battery sensor health tracking (93 sensors)

**Advanced Features - Phase 3 (2 files):**
- `energy_data.csv` - Energy and power sensors with automatic categorization
  - Categories: solar_production, grid_consumption, grid_export, energy_consumption, power_usage, electrical_monitoring
- `automation_context.csv` - User-editable automation purposes (preserved across syncs)

**Persons & Presence (1 file):**
- `persons_presence.csv` - Household members, device trackers, occupancy sensors
  - GPS tracking for persons
  - Network device tracking
  - Room-level occupancy detection

#### Output Formats
- **Table** - Human-readable tables (default)
- **JSON** - For scripting and automation
- **YAML** - For configuration management
- **CSV** - For data analysis
- **Detail** - Verbose information display

#### Testing
- **87 Integration Tests** - Comprehensive test coverage
- **65 pytest Tests** - Unit and integration tests
  - 20 memory-specific tests
  - Test all sync functions individually
  - Validate CSV structure and data correctness
  - Test user edit preservation across syncs
- **11 Handler Tests** - Memory sync validation
  - Tests for all 8 Phase 1-3 sync functions
  - CSV creation and structure validation
  - User annotation preservation testing

#### Security & Privacy
- Environment-based configuration (`.env` file)
- No hardcoded secrets or credentials
- `.gitignore` protects private data:
  - `memory/` - Private AI context (gitignored)
  - `generated/` - AI-generated configs (gitignored)
  - `.env` - Credentials (gitignored)

#### Documentation
- **README.md** - User-facing documentation with examples
- **AGENTS.md** - Comprehensive AI assistant guide
  - Memory system architecture
  - All 17 CSV file formats with examples
  - Phase 1, 2, 3 feature explanations
  - Persons & presence tracking guide
- **test/README.md** - Test suite documentation
- **Setup Guide** - Installation instructions for mise and standard Python

### Technical Details

- **Python 3.8+** compatibility
- **Click Framework** for CLI interface
- **WebSocket API** support for real-time data
- **REST API** integration for Home Assistant
- **CSV Format** for memory (90% smaller than JSON)
- **Kubernetes Support** via kubectl integration
- **Comprehensive Error Handling** with helpful messages

### Installation

```bash
# Clone and install
git clone https://github.com/nachtschatt3n/hactl.git
cd hactl
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your Home Assistant URL and token

# Verify
hactl --version
hactl get devices
```

### Dependencies

- click >= 8.0.0
- requests >= 2.25.0
- pyyaml >= 5.4.0
- python-dotenv >= 0.19.0
- websocket-client >= 1.0.0
- tabulate >= 0.8.9

### License

MIT License - See LICENSE file for details

### Author

Mathias Uhl ([@nachtschatt3n](https://github.com/nachtschatt3n))

---

## Future Releases

See [GitHub Issues](https://github.com/nachtschatt3n/hactl/issues) for planned features and enhancements.
