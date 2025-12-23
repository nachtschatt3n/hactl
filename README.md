# hactl - Home Assistant Control CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-49%20passing-brightgreen.svg)](test/)

A powerful kubectl-style command-line interface for managing Home Assistant via API. Control your smart home from the terminal with 47 commands organized into intuitive command groups.

## ✨ Features

- **🎯 kubectl-style Interface** - Familiar command structure for DevOps engineers
- **📊 Multiple Output Formats** - table, JSON, YAML, CSV, and detail views
- **🔋 Battery Monitoring** - Track all battery-powered devices
- **☸️ Kubernetes Integration** - Direct config updates for K8s deployments
- **🤖 AI Memory System** - Store contextual information about your home
- **⚡ AI Generation** - Generate dashboards and automations from descriptions
- **🧪 100% Test Coverage** - 49 comprehensive tests
- **🔒 Secure** - Environment-based configuration, no hardcoded secrets

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/nachtschatt3n/hactl.git
cd hactl

# Install in development mode
pip install -e .

# Verify installation
hactl --version
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

# Sync Home Assistant state to AI memory
hactl memory sync

# Generate a dashboard from description
hactl generate dashboard "energy monitoring with solar panels"
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

### K8S - Kubernetes Operations (2 commands)

```bash
# Update Home Assistant config via kubectl
hactl k8s update-config <helper_file> --namespace <namespace>

# Find Home Assistant pod
hactl k8s find-pod --namespace <namespace>
```

### MEMORY - AI Context Management (5 commands)

```bash
# Add contextual note
hactl memory add sensor bedroom_temp "Reads 2°C high, needs calibration"

# Show notes for a category
hactl memory show sensor

# Edit memory files
hactl memory edit context/preferences.md

# Sync Home Assistant state to memory
hactl memory sync
hactl memory sync --category sensors
```

### GENERATE - AI-Assisted Creation (6 commands)

```bash
# Generate dashboard
hactl generate dashboard "energy monitoring with solar production"

# Generate automation
hactl generate automation "turn off lights when no motion for 10 minutes"

# Generate blueprint
hactl generate blueprint "motion-activated lighting for any room"

# List generated content
hactl generate list

# Apply generated content
hactl generate apply generated/dashboards/2024-01-15_energy_monitoring.yaml
```

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
