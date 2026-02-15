"""
Tests for devices handler (business logic)
"""

import pytest
import json
from hactl.handlers import devices


class TestGetDevices:
    """Test get_devices handler function"""

    def test_get_devices_table_format(self, mock_env_vars, mock_websocket, capsys):
        """Test devices handler with table format"""
        devices.get_devices(format_type='table')

        output = capsys.readouterr().out
        assert 'Home Assistant Devices' in output
        assert 'Total Devices: 3' in output
        assert 'Living Room Light' in output
        assert 'Philips' in output
        assert 'Temperature Sensor' in output

    def test_get_devices_json_format(self, mock_env_vars, mock_websocket, capsys):
        """Test devices handler with JSON format"""
        devices.get_devices(format_type='json')

        output = capsys.readouterr().out
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 3

        names = [d.get('name') for d in data]
        assert 'Living Room Light' in names
        assert 'Temperature Sensor' in names

    def test_get_devices_yaml_format(self, mock_env_vars, mock_websocket, capsys):
        """Test devices handler with YAML format"""
        devices.get_devices(format_type='yaml')

        output = capsys.readouterr().out
        assert 'Home Assistant Devices' in output
        assert 'name:' in output
        assert 'Living Room Light' in output

    def test_get_devices_detail_format(self, mock_env_vars, mock_websocket, capsys):
        """Test devices handler with detail format"""
        devices.get_devices(format_type='detail')

        output = capsys.readouterr().out
        assert 'Home Assistant Devices' in output
        assert 'Total Devices: 3' in output
        assert 'Living Room Light' in output
        assert 'Manufacturer: Philips' in output
        assert 'Model: Hue White' in output

    def test_get_devices_handles_integer_model(self, mock_env_vars, mock_websocket, capsys):
        """Test that integer model values are handled correctly"""
        devices.get_devices(format_type='table')

        output = capsys.readouterr().out
        # model=110 for Smart Plug should not crash
        assert 'Smart Plug' in output or 'Kitchen Plug' in output


class TestDevicesErrorHandling:
    """Test error handling in devices handler"""

    def test_missing_hass_url(self, monkeypatch):
        """Test error when HASS_URL is not set"""
        monkeypatch.delenv('HASS_URL', raising=False)
        monkeypatch.delenv('HASS_TOKEN', raising=False)
        monkeypatch.setattr('hactl.core.config.load_dotenv', lambda: None)

        with pytest.raises(Exception) as exc_info:
            devices.get_devices()

        assert 'HASS_URL' in str(exc_info.value) or 'Error' in str(exc_info.type)
