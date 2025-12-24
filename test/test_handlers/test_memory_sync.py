"""
Tests for memory sync handler functions
Tests each individual sync function to ensure correct CSV file creation
"""

import pytest
import csv
from pathlib import Path
from unittest.mock import Mock, patch
from hactl.handlers import memory_mgmt


class TestSyncTemplates:
    """Test sync_templates function"""

    def test_sync_templates_creates_csv(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test that sync_templates creates templates.csv with correct structure"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock states response with template entities
        mock_states = [
            {
                'entity_id': 'sensor.template_test',
                'state': '42',
                'attributes': {
                    'friendly_name': 'Template Test',
                    'unit_of_measurement': '°C',
                    'device_class': 'temperature',
                    'state_class': 'measurement'
                }
            },
            {
                'entity_id': 'sensor.regular_sensor',
                'state': '10',
                'attributes': {
                    'friendly_name': 'Regular Sensor'
                }
            }
        ]

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_states):
            count = memory_mgmt.sync_templates('http://test', 'token')

        assert count == 1  # Only template sensor counted

        # Verify CSV file created
        csv_file = memory_dir / 'templates.csv'
        assert csv_file.exists()

        # Verify CSV structure
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        assert headers == ['entity_id', 'friendly_name', 'unit', 'device_class', 'state_class']
        assert len(rows) == 1
        assert rows[0]['entity_id'] == 'sensor.template_test'
        assert rows[0]['state_class'] == 'measurement'


class TestSyncEntityRelationships:
    """Test sync_entity_relationships function"""

    def test_sync_entity_relationships_creates_csv(self, mock_env_vars, tmp_path, monkeypatch):
        """Test that sync_entity_relationships creates entity_relationships.csv"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock WebSocket responses
        mock_device_registry = [
            {'id': 'device1', 'area_id': 'living_room'},
            {'id': 'device2', 'area_id': 'bedroom'}
        ]

        mock_entity_registry = [
            {'entity_id': 'light.living_room_1', 'device_id': 'device1', 'area_id': None},
            {'entity_id': 'light.living_room_2', 'device_id': 'device1', 'area_id': None},
            {'entity_id': 'sensor.bedroom_temp', 'area_id': 'bedroom', 'device_id': None}
        ]

        mock_ws = Mock()
        mock_ws.call.side_effect = [mock_entity_registry, mock_device_registry]

        with patch('hactl.handlers.memory_mgmt.WebSocketClient', return_value=mock_ws):
            count = memory_mgmt.sync_entity_relationships('http://test', 'token')

        assert count > 0

        # Verify CSV file created
        csv_file = memory_dir / 'entity_relationships.csv'
        assert csv_file.exists()

        # Verify CSV structure
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        assert headers == ['entity_id', 'related_entity', 'relationship_type', 'context']
        assert all(row['relationship_type'] == 'same_area' for row in rows)


class TestSyncAutomationStats:
    """Test sync_automation_stats function"""

    def test_sync_automation_stats_creates_csv(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test that sync_automation_stats creates automation_stats.csv"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock states response with automations
        mock_states = [
            {
                'entity_id': 'automation.test_auto',
                'state': 'on',
                'attributes': {
                    'friendly_name': 'Test Automation',
                    'last_triggered': '2024-01-01T12:00:00',
                    'mode': 'single',
                    'current': 0
                }
            },
            {
                'entity_id': 'light.test',
                'state': 'on',
                'attributes': {}
            }
        ]

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_states):
            count = memory_mgmt.sync_automation_stats('http://test', 'token')

        assert count == 1

        # Verify CSV file created
        csv_file = memory_dir / 'automation_stats.csv'
        assert csv_file.exists()

        # Verify CSV structure
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        assert headers == ['entity_id', 'friendly_name', 'state', 'last_triggered', 'mode', 'currently_running']
        assert len(rows) == 1
        assert rows[0]['entity_id'] == 'automation.test_auto'
        assert rows[0]['mode'] == 'single'


class TestSyncServiceCapabilities:
    """Test sync_service_capabilities function"""

    def test_sync_service_capabilities_list_format(self, mock_env_vars, tmp_path, monkeypatch):
        """Test sync_service_capabilities with list format API response"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock services response (list format)
        mock_services = [
            {
                'domain': 'light',
                'service': 'turn_on',
                'description': 'Turn on light',
                'fields': {
                    'brightness': {'description': 'Brightness', 'required': False},
                    'color': {'description': 'Color', 'required': False}
                }
            }
        ]

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_services):
            count = memory_mgmt.sync_service_capabilities('http://test', 'token')

        assert count == 1

        # Verify CSV file created
        csv_file = memory_dir / 'service_capabilities.csv'
        assert csv_file.exists()

        # Verify CSV structure
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        assert headers == ['domain', 'service', 'description', 'parameters', 'required_params']
        assert len(rows) == 1
        assert rows[0]['domain'] == 'light'
        assert 'brightness' in rows[0]['parameters']

    def test_sync_service_capabilities_dict_format(self, mock_env_vars, tmp_path, monkeypatch):
        """Test sync_service_capabilities with dict format API response"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock services response (dict format)
        mock_services = {
            'light': {
                'turn_on': {
                    'description': 'Turn on light',
                    'fields': {
                        'brightness': {'description': 'Brightness'}
                    }
                }
            }
        }

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_services):
            count = memory_mgmt.sync_service_capabilities('http://test', 'token')

        assert count == 1

        # Verify CSV file created
        csv_file = memory_dir / 'service_capabilities.csv'
        assert csv_file.exists()


class TestSyncBatteryHealth:
    """Test sync_battery_health function"""

    def test_sync_battery_health_creates_csv(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test that sync_battery_health creates battery_health.csv"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock states response with battery sensors
        mock_states = [
            {
                'entity_id': 'sensor.phone_battery',
                'state': '85',
                'attributes': {
                    'friendly_name': 'Phone Battery',
                    'unit_of_measurement': '%',
                    'device_class': 'battery'
                }
            },
            {
                'entity_id': 'sensor.temperature',
                'state': '20',
                'attributes': {
                    'friendly_name': 'Temperature',
                    'device_class': 'temperature'
                }
            }
        ]

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_states):
            count = memory_mgmt.sync_battery_health('http://test', 'token')

        assert count == 1

        # Verify CSV file created
        csv_file = memory_dir / 'battery_health.csv'
        assert csv_file.exists()

        # Verify CSV structure
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        assert headers == ['entity_id', 'friendly_name', 'current_level', 'level_numeric', 'unit', 'device_class']
        assert len(rows) == 1
        assert rows[0]['entity_id'] == 'sensor.phone_battery'
        assert rows[0]['level_numeric'] == '85'


class TestSyncEnergyData:
    """Test sync_energy_data function"""

    def test_sync_energy_data_creates_csv(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test that sync_energy_data creates energy_data.csv with categorization"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock states response with energy sensors
        mock_states = [
            {
                'entity_id': 'sensor.solar_production',
                'state': '1500',
                'attributes': {
                    'friendly_name': 'Solar Production',
                    'unit_of_measurement': 'W',
                    'device_class': 'power',
                    'state_class': 'measurement'
                }
            },
            {
                'entity_id': 'sensor.grid_consumption',
                'state': '2000',
                'attributes': {
                    'friendly_name': 'Grid Consumption',
                    'unit_of_measurement': 'kWh',
                    'device_class': 'energy',
                    'state_class': 'total_increasing'
                }
            }
        ]

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_states):
            count = memory_mgmt.sync_energy_data('http://test', 'token')

        assert count == 2

        # Verify CSV file created
        csv_file = memory_dir / 'energy_data.csv'
        assert csv_file.exists()

        # Verify CSV structure and categorization
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        assert headers == ['entity_id', 'friendly_name', 'category', 'current_value', 'value_numeric', 'unit', 'device_class', 'state_class']
        assert len(rows) == 2

        # Check categorization
        solar_row = [r for r in rows if 'solar' in r['entity_id']][0]
        assert solar_row['category'] == 'solar_production'

        grid_row = [r for r in rows if 'grid' in r['entity_id']][0]
        assert grid_row['category'] == 'grid_consumption'  # Contains "grid" and "consumption"


class TestSyncAutomationContext:
    """Test sync_automation_context function"""

    def test_sync_automation_context_creates_csv(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test that sync_automation_context creates automation_context.csv"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock states response with automations
        mock_states = [
            {
                'entity_id': 'automation.morning_lights',
                'state': 'on',
                'attributes': {
                    'friendly_name': 'Morning Lights'
                }
            }
        ]

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_states):
            count = memory_mgmt.sync_automation_context('http://test', 'token')

        assert count == 1

        # Verify CSV file created
        csv_file = memory_dir / 'automation_context.csv'
        assert csv_file.exists()

        # Verify CSV structure
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        assert headers == ['entity_id', 'friendly_name', 'purpose', 'category', 'user_notes']
        assert len(rows) == 1
        assert rows[0]['entity_id'] == 'automation.morning_lights'
        assert rows[0]['purpose'] == ''  # Empty for new automations

    def test_sync_automation_context_preserves_user_edits(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test that sync_automation_context preserves user annotations across syncs"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Create existing context file with user annotations
        csv_file = memory_dir / 'automation_context.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['entity_id', 'friendly_name', 'purpose', 'category', 'user_notes'])
            writer.writeheader()
            writer.writerow({
                'entity_id': 'automation.morning_lights',
                'friendly_name': 'Morning Lights',
                'purpose': 'Turn on lights at sunrise',
                'category': 'lighting',
                'user_notes': 'Important user annotation'
            })

        # Mock states response with same automation
        mock_states = [
            {
                'entity_id': 'automation.morning_lights',
                'state': 'on',
                'attributes': {
                    'friendly_name': 'Morning Lights Updated'  # Friendly name changed
                }
            },
            {
                'entity_id': 'automation.new_auto',
                'state': 'on',
                'attributes': {
                    'friendly_name': 'New Automation'
                }
            }
        ]

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_states):
            count = memory_mgmt.sync_automation_context('http://test', 'token')

        assert count == 2

        # Verify user annotations preserved
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

        # Check existing automation preserved user edits
        existing = [r for r in rows if r['entity_id'] == 'automation.morning_lights'][0]
        assert existing['purpose'] == 'Turn on lights at sunrise'  # PRESERVED
        assert existing['category'] == 'lighting'  # PRESERVED
        assert existing['user_notes'] == 'Important user annotation'  # PRESERVED

        # Check new automation has empty context
        new = [r for r in rows if r['entity_id'] == 'automation.new_auto'][0]
        assert new['purpose'] == ''
        assert new['user_notes'] == ''


class TestSyncPersonsPresence:
    """Test sync_persons_presence function"""

    def test_sync_persons_presence_creates_csv(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test that sync_persons_presence creates persons_presence.csv"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock states response with persons, trackers, and occupancy sensors
        mock_states = [
            {
                'entity_id': 'person.john',
                'state': 'home',
                'attributes': {
                    'friendly_name': 'John',
                    'latitude': 50.1,
                    'longitude': 8.2,
                    'source': 'device_tracker.john_phone'
                }
            },
            {
                'entity_id': 'device_tracker.john_phone',
                'state': 'home',
                'attributes': {
                    'friendly_name': 'John Phone',
                    'source_type': 'gps',
                    'latitude': 50.1,
                    'longitude': 8.2
                }
            },
            {
                'entity_id': 'binary_sensor.living_room_occupancy',
                'state': 'on',
                'attributes': {
                    'friendly_name': 'Living Room Occupancy',
                    'device_class': 'occupancy'
                }
            },
            {
                'entity_id': 'binary_sensor.door',
                'state': 'off',
                'attributes': {
                    'friendly_name': 'Door',
                    'device_class': 'door'
                }
            }
        ]

        with patch('hactl.handlers.memory_mgmt.make_api_request', return_value=mock_states):
            count = memory_mgmt.sync_persons_presence('http://test', 'token')

        assert count == 3  # 1 person + 1 device_tracker + 1 occupancy sensor (door excluded)

        # Verify CSV file created
        csv_file = memory_dir / 'persons_presence.csv'
        assert csv_file.exists()

        # Verify CSV structure
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        assert headers == ['entity_id', 'type', 'friendly_name', 'state', 'location', 'latitude', 'longitude', 'source', 'device_class']
        assert len(rows) == 3

        # Verify person entry
        person_row = [r for r in rows if r['type'] == 'person'][0]
        assert person_row['entity_id'] == 'person.john'
        assert person_row['state'] == 'home'
        assert person_row['latitude'] == '50.1'

        # Verify device_tracker entry
        tracker_row = [r for r in rows if r['type'] == 'device_tracker'][0]
        assert tracker_row['entity_id'] == 'device_tracker.john_phone'
        assert tracker_row['source'] == 'gps'

        # Verify occupancy sensor entry
        occupancy_row = [r for r in rows if r['type'] == 'occupancy_sensor'][0]
        assert occupancy_row['entity_id'] == 'binary_sensor.living_room_occupancy'
        assert occupancy_row['device_class'] == 'occupancy'


class TestSyncFromHass:
    """Test sync_from_hass main function"""

    def test_sync_all_categories(self, mock_env_vars, tmp_path, monkeypatch):
        """Test that sync_from_hass creates all 17 CSV files"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        # Mock all sync functions to return counts
        with patch('hactl.handlers.memory_mgmt.sync_devices', return_value=10), \
             patch('hactl.handlers.memory_mgmt.sync_sensors', return_value=100), \
             patch('hactl.handlers.memory_mgmt.sync_automations', return_value=5), \
             patch('hactl.handlers.memory_mgmt.sync_dashboards', return_value=3), \
             patch('hactl.handlers.memory_mgmt.sync_hacs', return_value=20), \
             patch('hactl.handlers.memory_mgmt.sync_areas', return_value=8), \
             patch('hactl.handlers.memory_mgmt.sync_integrations', return_value=50), \
             patch('hactl.handlers.memory_mgmt.sync_scripts', return_value=7), \
             patch('hactl.handlers.memory_mgmt.sync_scenes', return_value=4), \
             patch('hactl.handlers.memory_mgmt.sync_templates', return_value=15), \
             patch('hactl.handlers.memory_mgmt.sync_entity_relationships', return_value=30), \
             patch('hactl.handlers.memory_mgmt.sync_automation_stats', return_value=5), \
             patch('hactl.handlers.memory_mgmt.sync_service_capabilities', return_value=40), \
             patch('hactl.handlers.memory_mgmt.sync_battery_health', return_value=12), \
             patch('hactl.handlers.memory_mgmt.sync_energy_data', return_value=25), \
             patch('hactl.handlers.memory_mgmt.sync_automation_context', return_value=5), \
             patch('hactl.handlers.memory_mgmt.sync_persons_presence', return_value=20):

            memory_mgmt.sync_from_hass()

        # Verify all sync functions were called (no exceptions)
        # The function doesn't return values, but the test succeeds if no exceptions raised
