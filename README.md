# hactl - Home Assistant Control CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-87%20total-brightgreen.svg)](test/)

A powerful kubectl-style command-line interface for managing Home Assistant via API. Control your smart home from the terminal with 41 commands organized into 5 intuitive command groups.

## ✨ Features

- **🎯 kubectl-style Interface** - Familiar command structure for DevOps engineers
- **📊 Multiple Output Formats** - table, JSON, YAML, CSV, and detail views
- **🔋 Battery Monitoring** - Track all battery-powered devices
- **☸️ Kubernetes Integration** - Direct config updates for K8s deployments
- **🧪 Comprehensive Testing** - 87 integration tests with comprehensive memory sync validation
- **🔒 Secure** - Environment-based configuration, no hardcoded secrets
- **🤖 AI-Friendly** - Perfect tool for AI assistants to manage Home Assistant

## 🚀 Quick Start

### Installation

#### Option 1: With mise (Recommended)

If you use [mise](https://mise.jdx.dev/) for version management:

```bash
# Clone the repository
git clone https://github.com/nachtschatt3n/hactl.git
cd hactl

# mise will automatically activate the Python version from .mise.toml
# and create a virtual environment

# Install in development mode
pip install -e .

# Verify installation
hactl --version
```

#### Option 2: Standard Python Installation

```bash
# Clone the repository
git clone https://github.com/nachtschatt3n/hactl.git
cd hactl

# Create virtual environment (Python 3.8+)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Verify installation
hactl --version
```

#### Option 3: Install from PyPI (when published)

```bash
pip install hactl
```

### Configuration

Create a `.env` file with your Home Assistant credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
HASS_URL="https://your-homeassistant-url.com"
HASS_TOKEN="your_long_lived_access_token_here"

# Optional: For K8s commands
K8S_NAMESPACE="home-automation"
```

**Getting a Long-Lived Access Token:**
1. Open your Home Assistant instance
2. Click your profile (bottom-left)
3. Scroll to "Long-Lived Access Tokens"
4. Click "Create Token"
5. Copy the token and add it to `.env`

### Basic Usage

```bash
# Get all devices
hactl get devices

# Get devices in JSON format
hactl get devices --format json

# Get battery sensors
hactl get sensors battery

# List battery-powered devices
hactl battery list

# Update a dashboard
hactl update dashboard my-dashboard --from dashboard.yaml
```

## 📚 Command Groups

### GET - Read Resources (29 commands)

```bash
hactl get devices                    # All devices
hactl get states                     # All entity states
hactl get states --domain light      # Filter by domain
hactl get sensors <type>             # Sensors by type
hactl get integrations               # Configured integrations
hactl get automations                # All automations
hactl get dashboards                 # All dashboards
hactl get services                   # Available services

# And 21 more commands for scenes, scripts, helpers, calendars, etc.
```

**Supported sensor types:** battery, temperature, humidity, co2, power, energy, pressure, motion, etc.

### UPDATE - Modify Resources (2 commands)

```bash
# Update dashboard from YAML file
hactl update dashboard <url_path> --from <yaml_file>

# Create new dashboard
hactl update dashboard <url_path> --from <yaml_file> --create

# Update helper configuration
hactl update helper <yaml_file>
```

### BATTERY - Monitoring Utilities (3 commands)

```bash
# List all battery devices
hactl battery list

# Exclude mobile devices
hactl battery list --exclude-mobile

# Check battery summary sensors
hactl battery check

# Create battery monitoring setup
hactl battery monitor
```

### K8S - Kubernetes Operations (4 commands)

```bash
# Find Home Assistant pod
hactl k8s find-pod --namespace <namespace>

# Download configuration from pod
hactl k8s get-config --output config.yaml
hactl k8s get-config --file /config/templates.yaml --output templates.yaml

# Upload configuration to pod (with backup and restart)
hactl k8s put-config config.yaml
hactl k8s put-config templates.yaml --file /config/templates.yaml --no-restart

# Update config with helper sensors (automated merge)
hactl k8s update-config battery-summary.yaml --namespace <namespace>
```

### MEMORY - AI Context Management (5 commands)

The memory system helps AI assistants maintain context about your Home Assistant setup. It stores Home Assistant state as **compact CSV files** for token-efficient reading, reducing the need to repeatedly query all states.

```bash
# Sync current HA state to memory/  (creates CSV files)
hactl memory sync

# List all memory files
hactl memory list

# Add contextual notes for AI
hactl memory add sensor bedroom_temp "Reads 2°C high, needs calibration"

# Show memory for a category
hactl memory show sensors

# Edit memory files directly
hactl memory edit context/preferences.md
```

**Memory files created by sync:**
- `devices.csv` - All devices with manufacturer, model, area (472 devices)
- `states.csv` - All entity states with current values (2249 entities)
- `automations.csv` - All automations with status (4 automations)
- `dashboards.csv` - All dashboards with titles (5 dashboards)
- `hacs.csv` - Installed HACS repositories with versions and descriptions (44 repos)
- `areas.csv` - All areas (rooms/zones) with names and aliases (19 areas)
- `integrations.csv` - All configured integrations with state (155 integrations)
- `scripts.csv` - All scripts with last triggered time
- `scenes.csv` - All scenes with icons (14 scenes)
- `templates.csv` - Template sensors with formulas and state classes (478 templates)
- `entity_relationships.csv` - Entity relationships and groupings (352 relationships)
- `automation_stats.csv` - Automation statistics and execution history (4 automations)
- `service_capabilities.csv` - Available service domains (86 domains)
- `battery_health.csv` - Battery sensor health tracking
- `energy_data.csv` - Energy and power sensors for optimization
- `automation_context.csv` - User annotations about automation purposes (editable)
- `persons_presence.csv` - Household members, device trackers, and occupancy sensors

**Note:** The memory/ directory is gitignored and not committed. AI assistants can read these compact CSV files to quickly understand your entire setup in just a few thousand tokens.

## 🎨 Output Formats

Most commands support multiple output formats:

```bash
# Human-readable table (default)
hactl get devices

# JSON for scripting
hactl get devices --format json | jq '.[0]'

# YAML format
hactl get devices --format yaml

# Detailed information
hactl get states --format detail
```

## 📖 Examples

### Monitor Battery Levels

```bash
# Get all battery sensors
hactl get sensors battery

# List battery devices (excluding phones/tablets)
hactl battery list --exclude-mobile

# Get JSON output for scripting
hactl battery list --format json | jq '.[] | select(.level < 20)'
```

### Dashboard Management

```bash
# List all dashboards
hactl get dashboards

# Export dashboard to YAML
hactl get dashboards --format yaml-single --url-path my-dashboard > backup.yaml

# Export specific VIEW from dashboard (new feature!)
hactl get dashboards --format yaml-single --url-path my-dashboard/my-view > view.yaml

# Validate dashboard entities (checks against current HA state)
hactl get dashboards --format validate --url-path my-dashboard/my-view

# Update dashboard
hactl update dashboard my-dashboard --from backup.yaml
```

### Automation Management

```bash
# Get all automations
hactl get automations

# Get automations in JSON
hactl get automations --format json

# Get detailed automation info
hactl get automations --format detail
```

## 🏗️ Project Structure

```
hactl/
├── cli.py                 # Main Click entry point
├── core/                  # Core utilities
│   ├── config.py         # Configuration management
│   ├── api.py            # API request handling
│   ├── formatting.py     # Output formatting
│   └── websocket.py      # WebSocket client
├── commands/             # Command groups (6 files)
│   ├── get.py           # GET commands
│   ├── update.py        # UPDATE commands
│   ├── battery.py       # BATTERY commands
│   ├── k8s.py           # K8S commands
│   ├── memory.py        # MEMORY commands
│   └── generate.py      # GENERATE commands
└── handlers/            # Business logic (30+ files)
    ├── devices.py
    ├── sensors.py
    ├── dashboards.py
    └── ...
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest test/test_commands/test_get_commands.py

# Run with coverage
pytest --cov=hactl --cov-report=html
```

**Current test status:** ✅ 49/49 tests passing (100%)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Mathias Uhl**
- GitHub: [@nachtschatt3n](https://github.com/nachtschatt3n)

## 🙏 Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) - Python CLI framework
- Inspired by [kubectl](https://kubernetes.io/docs/reference/kubectl/) - Kubernetes CLI
- For [Home Assistant](https://www.home-assistant.io/) - Open source home automation

## 📚 Related Documentation

- **[CLAUDE.md](CLAUDE.md)** - Detailed technical documentation for AI assistants and developers
- **[test/README.md](test/README.md)** - Test suite documentation

---

**Star ⭐ this repository if you find it useful!**
