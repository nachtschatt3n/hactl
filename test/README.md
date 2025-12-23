# Test Suite

This directory contains comprehensive tests for all Home Assistant API scripts.

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest test/test_get_devices.py
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test function
```bash
pytest test/test_get_devices.py::test_devices_table_output
```

### Run tests with coverage
```bash
pytest --cov=get --cov=update --cov-report=html
```

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_get_*.py` - Tests for get scripts
- `test_update_*.py` - Tests for update scripts
- `test_common.py` - Tests for common utilities

## Test Coverage

All scripts are tested for:
- Table output format
- JSON output format
- YAML output format
- Detail output format (where applicable)
- Error handling
- Edge cases

## Mocking

Tests use mocked API responses to avoid hitting the real Home Assistant API. All API calls are intercepted and return predefined test data.
