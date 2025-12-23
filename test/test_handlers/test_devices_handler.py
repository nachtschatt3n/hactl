"""
Tests for devices handler (business logic)
"""

import pytest
import json
from hactl.handlers import devices


class TestGetDevices:
    """Test get_devices handler function"""

    def test_get_devices_table_format(self, mock_env_vars, mock_api_request, capsys):
        """Test devices handler with table format"""
        devices.get_devices(format_type='table')

        output = capsys.readouterr().out
        assert 'sensor.temperature' in output
        assert 'light.living_room' in output

    def test_get_devices_json_format(self, mock_env_vars, mock_api_request, capsys):
        """Test devices handler with JSON format"""
        devices.get_devices(format_type='json')

        output = capsys.readouterr().out
        # Verify it's valid JSON
        data = json.loads(output)
        assert isinstance(data, list)

        # Check for expected entities
        entity_ids = [item['entity_id'] for item in data]
        assert 'sensor.temperature' in entity_ids
        assert 'light.living_room' in entity_ids

    def test_get_devices_yaml_format(self, mock_env_vars, mock_api_request, capsys):
        """Test devices handler with YAML format"""
        devices.get_devices(format_type='yaml')

        output = capsys.readouterr().out
        assert 'entity_id:' in output
        assert 'sensor.temperature' in output

    def test_get_devices_detail_format(self, mock_env_vars, mock_api_request, capsys):
        """Test devices handler with detail format"""
        devices.get_devices(format_type='detail')

        output = capsys.readouterr().out
        assert 'sensor.temperature' in output
        # Detail format should show attributes
        assert 'Attributes:' in output or 'friendly_name' in output


class TestDevicesErrorHandling:
    """Test error handling in devices handler"""

    def test_missing_hass_url(self, monkeypatch, capsys):
        """Test error when HASS_URL is not set"""
        # Don't set HASS_URL
        monkeypatch.delenv('HASS_URL', raising=False)
        monkeypatch.delenv('HASS_TOKEN', raising=False)

        with pytest.raises(Exception) as exc_info:
            devices.get_devices()

        # Should raise ClickException with appropriate message
        assert 'HASS_URL' in str(exc_info.value) or 'Error' in str(exc_info.type)
