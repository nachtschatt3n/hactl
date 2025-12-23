# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

**hactl** is a kubectl-style command-line interface for managing Home Assistant via API. It provides a unified CLI tool that replaces 30+ individual Python scripts with a single command interface using the Click framework.

**Home Assistant Instance:** Configured via environment variables (`.env` file)

**Command Structure:** `hactl <verb> <resource> [options]`

## Quick Reference

### Common Commands

```bash
# Installation
pip install -e .

# Get resources
hactl get devices
hactl get devices --format json
hactl get sensors battery
hactl get states --entity sensor.temperature

# Update resources
hactl update dashboard battery-monitor --from dashboard.yaml

# Battery monitoring
hactl battery list
hactl battery check

# AI memory
hactl memory sync
hactl memory add sensor bedroom_temp "Reads 2°C high"

# AI generation
hactl generate dashboard "energy monitoring"
hactl generate list

# Kubernetes
hactl k8s find-pod
hactl k8s update-config helper.yaml

# Testing
pytest
pytest test/test_commands/
pytest -v
```

## Project Structure

```
cberg-home-assistant/
├── hactl/                          # Main package
│   ├── __init__.py                 # Package initialization
│   ├── cli.py                      # Main Click entry point (47 commands)
│   ├── core/                       # Core utilities
│   │   ├── __init__.py
│   │   ├── config.py               # load_config() - env var loading
│   │   ├── api.py                  # make_api_request() - HTTP requests
│   │   ├── formatting.py           # format_output(), json_to_yaml()
│   │   └── websocket.py            # WebSocketClient for dashboards
│   ├── commands/                   # Click command groups
│   │   ├── __init__.py
│   │   ├── get.py                  # GET commands (29 commands)
│   │   ├── update.py               # UPDATE commands (2 commands)
│   │   ├── battery.py              # BATTERY commands (3 commands)
│   │   ├── k8s.py                  # K8S commands (2 commands)
│   │   ├── memory.py               # MEMORY commands (5 commands)
│   │   └── generate.py             # GENERATE commands (6 commands)
│   └── handlers/                   # Business logic (30+ handlers)
│       ├── devices.py              # Device operations
│       ├── states.py               # State management
│       ├── sensors.py              # Sensor operations
│       ├── integrations.py         # Integration management
│       ├── dashboards.py           # Dashboard operations
│       ├── automations_scripts_helpers.py  # Automations/scripts/helpers
│       ├── battery_monitor.py      # Battery monitoring
│       ├── k8s_config.py           # Kubernetes operations
│       ├── memory_mgmt.py          # AI memory management
│       ├── ai_generator.py         # AI content generation
│       └── ... (20+ more handlers)
├── memory/                         # AI context (gitignored)
│   ├── README.md                   # Memory system documentation
│   ├── sensors/                    # Sensor context and notes
│   ├── devices/                    # Device context and notes
│   ├── dashboards/                 # Dashboard context
│   ├── automations/                # Automation context
│   └── context/                    # General AI context
│       ├── ai_instructions.md      # AI generation instructions
│       └── preferences.md          # User automation preferences
├── generated/                      # AI-generated content (gitignored)
│   ├── README.md                   # Generated content documentation
│   ├── dashboards/                 # Generated dashboard YAML
│   ├── automations/                # Generated automation YAML
│   ├── blueprints/                 # Generated blueprint YAML
│   └── scripts/                    # Generated script YAML
├── test/                           # Test suite (49 tests, 100% passing)
│   ├── conftest.py                 # Shared fixtures and mocks
│   ├── test_commands/              # Click CLI tests
│   │   ├── test_get_commands.py    # GET command tests
│   │   ├── test_battery_commands.py
│   │   ├── test_memory_commands.py
│   │   └── test_generate_commands.py
│   └── test_handlers/              # Handler business logic tests
│       └── test_devices_handler.py
├── setup.py                        # Package configuration
├── requirements.txt                # Dependencies (click, python-dotenv, pyyaml)
├── .env.example                    # Example environment file
├── .gitignore                      # Ignores .env, memory/*, generated/*
├── pytest.ini                      # Pytest configuration
├── README.md                       # User documentation
├── CLAUDE.md                       # This file
└── validate_migration.py           # Validation script
```

## Architecture

### Click Framework

The project uses Click for CLI structure:

**Command Groups:**
- `get` - Read-only resource extraction (29 commands)
- `update` - Modify resources (2 commands)
- `battery` - Battery monitoring utilities (3 commands)
- `k8s` - Kubernetes operations (2 commands)
- `memory` - AI memory management (5 commands)
- `generate` - AI content generation (6 commands)

**Design Pattern:**
- Commands are in `hactl/commands/` using Click decorators
- Business logic is in `hactl/handlers/` as pure functions
- Core utilities in `hactl/core/` for shared functionality

### Core Utilities (`hactl/core/`)

#### `config.py`
```python
def load_config() -> Tuple[str, str]:
    """Load HASS_URL and HASS_TOKEN from environment.
    Raises click.ClickException if not set."""
```

- Uses `python-dotenv` to load `.env` file
- Raises `click.ClickException` instead of `sys.exit()`
- Always use this - never hardcode credentials

#### `api.py`
```python
def make_api_request(url: str, token: str, method: str = 'GET',
                     data: Optional[Dict] = None) -> Dict[str, Any]:
    """Make HTTP API request to Home Assistant.
    Raises click.ClickException on errors."""
```

- Uses `urllib.request` (no external dependencies)
- Automatically adds Authorization header
- Handles HTTP errors and timeouts
- Returns parsed JSON response

#### `formatting.py`
```python
def format_output(data, format_type, title):
    """Format data for console output."""

def json_to_yaml(obj, indent=0) -> str:
    """Convert JSON to YAML format."""
```

- Supports formats: `table`, `json`, `yaml`, `detail`
- Uses `click.echo()` for output
- Custom YAML converter (no PyYAML required)

#### `websocket.py`
```python
class WebSocketClient:
    """WebSocket client for Home Assistant dashboard operations."""
```

- Custom WebSocket implementation (no external dependencies)
- Used only for dashboard operations
- Handles authentication and message routing

### Handler Pattern

Handlers contain business logic and are called by Click commands:

```python
# hactl/handlers/devices.py
def get_devices(format_type='table'):
    """Get all devices from Home Assistant"""
    HASS_URL, HASS_TOKEN = load_config()
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)

    # Process data...

    if format_type == 'json':
        click.echo(json.dumps(data, indent=2))
    elif format_type == 'yaml':
        click.echo(json_to_yaml(data))
    else:  # table
        click.echo("=== Home Assistant Devices ===")
        # Format table output...
```

**Key patterns:**
- Functions take `format_type` parameter
- Use `click.echo()` instead of `print()`
- Raise `click.ClickException` instead of `sys.exit()`
- Import `load_config` and `make_api_request` from `hactl.core`

### Command Pattern

Commands are defined in `hactl/commands/` using Click decorators:

```python
# hactl/commands/get.py
@click.group('get')
def get_group():
    """Get resources from Home Assistant"""
    pass

@get_group.command('devices')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'yaml', 'detail']),
              default='table')
def get_devices(format):
    """Get all devices"""
    from hactl.handlers import devices
    devices.get_devices(format)
```

**Key patterns:**
- Use `@click.group()` for command groups
- Use `@click.command()` for individual commands
- Use `@click.option()` for flags/options
- Use `@click.argument()` for positional arguments
- Lazy import handlers (import inside function)
- Delegate to handler functions immediately

## Testing

### Test Structure

**Click CLI Tests (`test/test_commands/`):**
```python
from click.testing import CliRunner
from hactl.cli import cli

def test_get_devices(self, mock_env_vars, mock_api_request):
    runner = CliRunner()
    result = runner.invoke(cli, ['get', 'devices', '--format', 'table'])

    assert result.exit_code == 0
    assert 'Home Assistant Devices' in result.output
```

**Handler Tests (`test/test_handlers/`):**
```python
def test_devices_handler(self, mock_env_vars, mock_api_request, capsys):
    devices.get_devices(format_type='json')
    output = capsys.readouterr().out
    data = json.loads(output)
    assert isinstance(data, list)
```

### Fixtures (`test/conftest.py`)

**Key fixtures:**
- `mock_env_vars` - Sets HASS_URL and HASS_TOKEN
- `mock_api_request` - Mocks API responses
- `mock_states_response` - Sample entity states
- `mock_services_response` - Sample services
- `mock_integrations_response` - Sample integrations

**Mocking strategy:**
- Patches `hactl.core.api.make_api_request`
- Patches all handler imports (30+ handlers)
- Provides realistic mock data
- No actual API calls in tests

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest test/test_commands/test_get_commands.py

# Specific test class
pytest test/test_commands/test_get_commands.py::TestGetDevices

# Specific test function
pytest test/test_commands/test_get_commands.py::TestGetDevices::test_devices_table_format

# With verbose output
pytest -v

# With coverage
pytest --cov=hactl --cov-report=html

# Fast mode (short traceback)
pytest --tb=short
```

**Current status:** 49/49 tests passing (100%)

## Common Development Tasks

### Adding a New GET Command

1. **Create handler** (`hactl/handlers/my_resource.py`):
```python
import json
import click
from hactl.core import load_config, make_api_request

def get_my_resource(format_type='table'):
    """Get my resource from Home Assistant"""
    HASS_URL, HASS_TOKEN = load_config()
    url = f"{HASS_URL}/api/states"
    states = make_api_request(url, HASS_TOKEN)

    # Process data...

    if format_type == 'json':
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo("=== My Resource ===")
        # Format output...
```

2. **Add command** (`hactl/commands/get.py`):
```python
@get_group.command('my-resource')
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table')
def get_my_resource(format):
    """Get my resource"""
    from hactl.handlers import my_resource
    my_resource.get_my_resource(format)
```

3. **Add tests** (`test/test_commands/test_get_commands.py`):
```python
class TestGetMyResource:
    def test_my_resource_table(self, mock_env_vars, mock_api_request):
        runner = CliRunner()
        result = runner.invoke(cli, ['get', 'my-resource'])
        assert result.exit_code == 0
```

4. **Update conftest.py** if needed (add handler to patching list)

5. **Test it:**
```bash
pytest test/test_commands/test_get_commands.py::TestGetMyResource
hactl get my-resource
```

### Debugging Commands

```bash
# Run command with Python directly
python -m hactl.cli get devices

# Check command is registered
hactl --help
hactl get --help

# Test with mock data (use pytest fixtures)
pytest test/test_commands/ -v -s

# Check imports
python -c "from hactl.handlers import devices; print(dir(devices))"
```

### Modifying a Handler

1. Read the handler file
2. Make changes (preserve patterns)
3. Run handler tests: `pytest test/test_handlers/`
4. Run command tests: `pytest test/test_commands/`
5. Test manually: `hactl get <resource>`

## Environment Configuration

### Required Variables
- `HASS_URL` - Home Assistant URL (e.g., `https://homeassistant.local:8123`)
- `HASS_TOKEN` - Long-lived access token

### Loading Order
1. `.env` file (via `python-dotenv`)
2. Environment variables
3. Error if not set

### Security
- `.env` is gitignored
- Never commit tokens
- Never hardcode URLs/tokens in code
- Always use `load_config()`

## AI Memory & Generation

### Memory System (`memory/`)

Private directory (gitignored) for storing context about Home Assistant setup:

**Structure:**
- `sensors/` - Sensor notes and context
- `devices/` - Device notes and quirks
- `dashboards/` - Dashboard purposes
- `automations/` - Automation goals
- `context/` - General AI context
  - `ai_instructions.md` - Instructions for AI generation
  - `preferences.md` - User preferences

**Commands:**
```bash
hactl memory add sensor bedroom_temp "Reads 2°C high"
hactl memory show sensor
hactl memory sync  # Sync HA state to memory
hactl memory list  # List all memory contents
```

### Generation System (`generated/`)

Private directory (gitignored) for AI-generated configurations:

**Structure:**
- `dashboards/` - Generated dashboard YAML + manifest.json
- `automations/` - Generated automation YAML + manifest.json
- `blueprints/` - Generated blueprint YAML + manifest.json
- `scripts/` - Generated script YAML + manifest.json

**Commands:**
```bash
hactl generate dashboard "energy monitoring"
hactl generate automation "motion lights"
hactl generate list
hactl generate apply generated/dashboards/file.yaml
```

## Best Practices

### Code Style
1. Use Click patterns (`click.echo`, `click.ClickException`)
2. Separate commands (CLI) from handlers (logic)
3. Support multiple output formats
4. Use lazy imports in commands
5. Follow existing handler patterns

### Testing
1. Write tests for new commands (CLI + handler)
2. Use `CliRunner` for Click tests
3. Mock API calls (never call real API)
4. Test all output formats
5. Test error cases

### Error Handling
1. Use `click.ClickException` for user errors
2. Use `click.UsageError` for argument errors
3. Provide helpful error messages
4. Never use `sys.exit()` directly

### Documentation
1. Update README.md for new commands
2. Update this file (CLAUDE.md) for architecture changes
3. Add docstrings to handlers and commands
4. Include examples in command help text

## Troubleshooting

### "hactl: command not found"
```bash
pip install -e .  # Reinstall
which hactl       # Check PATH
python -m hactl.cli --help  # Use module directly
```

### "No module named 'hactl'"
```bash
pip install -e .  # Install package
echo $PYTHONPATH  # Check Python path
```

### Tests failing
```bash
# Check fixtures
pytest test/conftest.py -v

# Run single test
pytest test/test_commands/test_get_commands.py::TestGetDevices::test_devices_table_format -v

# Check mocking
pytest -v -s  # Show output
```

### API errors
```bash
# Check env vars
echo $HASS_URL
echo $HASS_TOKEN

# Test API directly
curl -H "Authorization: Bearer $HASS_TOKEN" $HASS_URL/api/

# Test hactl
hactl get integrations
```

## Important Files

**Must read before modifying:**
- `hactl/cli.py` - Main entry point, registers all command groups
- `hactl/core/config.py` - Environment variable loading
- `hactl/core/api.py` - HTTP API communication
- `test/conftest.py` - Test fixtures and mocking strategy

**Commonly modified:**
- `hactl/commands/get.py` - Adding new GET commands
- `hactl/handlers/*.py` - Modifying business logic
- `test/test_commands/*.py` - Adding command tests

**Configuration:**
- `setup.py` - Package configuration, entry points
- `requirements.txt` - Dependencies
- `.gitignore` - Ignored files (includes memory/, generated/)
- `pytest.ini` - Pytest configuration

## Migration Notes

This project was migrated from 30+ individual Python scripts to a unified `hactl` CLI tool:

**Old structure:**
- `get/*.py` - Individual scripts (25 scripts)
- `update/*.py` - Update scripts (2 scripts)
- `scripts/*.py` - Utility scripts (7 scripts)

**New structure:**
- `hactl` - Single unified CLI (47 commands)
- Kubectl-style command structure
- Click framework
- Comprehensive test suite

**Validation:**
- All old scripts have equivalent `hactl` commands
- Output format compatibility maintained
- 100% test coverage
- See `validate_migration.py` for equivalence testing

## Deployment Information

Home Assistant Instance: Configured via `.env` file
Deployment: Kubernetes-based (see `home-assistant.md` for deployment details)
