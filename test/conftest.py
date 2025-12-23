"""
Pytest configuration and fixtures for Home Assistant API tests
"""

import pytest
import json
import os
from unittest.mock import Mock, patch


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables"""
    monkeypatch.setenv('HASS_URL', 'https://test-hass.example.com')
    monkeypatch.setenv('HASS_TOKEN', 'test_token_12345')


@pytest.fixture
def mock_states_response():
    """Mock /api/states response"""
    return [
        {
            'entity_id': 'sensor.temperature',
            'state': '21.5',
            'attributes': {
                'friendly_name': 'Temperature',
                'unit_of_measurement': '°C',
                'device_class': 'temperature'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'light.living_room',
            'state': 'on',
            'attributes': {
                'friendly_name': 'Living Room Light',
                'brightness': 255
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'automation.test',
            'state': 'on',
            'attributes': {
                'friendly_name': 'Test Automation',
                'mode': 'single'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'scene.evening',
            'state': 'scening',
            'attributes': {
                'friendly_name': 'Evening Scene',
                'entity_id': ['light.living_room']
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'person.john',
            'state': 'home',
            'attributes': {
                'friendly_name': 'John',
                'device_trackers': ['device_tracker.phone']
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'zone.home',
            'state': 'zoning',
            'attributes': {
                'friendly_name': 'Home',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'radius': 100
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'sensor.battery_level',
            'state': '85',
            'attributes': {
                'friendly_name': 'Battery Level',
                'device_class': 'battery',
                'unit_of_measurement': '%'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'calendar.work',
            'state': 'on',
            'attributes': {
                'friendly_name': 'Work Calendar',
                'message': 'Meeting at 2pm'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'todo.shopping',
            'state': '3',
            'attributes': {
                'friendly_name': 'Shopping List'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'persistent_notification.config_entry_discovery',
            'state': 'notifying',
            'attributes': {
                'title': 'New Device Found',
                'message': 'A new device has been discovered',
                'created_at': '2024-01-01T12:00:00Z'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'sensor.hacs_version',
            'state': '1.30.0',
            'attributes': {
                'friendly_name': 'HACS Version',
                'device_class': 'update'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'template.test_template',
            'state': '42',
            'attributes': {
                'friendly_name': 'Test Template',
                'device_class': 'temperature'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'media_player.living_room',
            'state': 'playing',
            'attributes': {
                'friendly_name': 'Living Room Speaker',
                'media_title': 'Song Title',
                'media_artist': 'Artist Name',
                'volume_level': 0.5
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'camera.front_door',
            'state': 'idle',
            'attributes': {
                'friendly_name': 'Front Door Camera',
                'brand': 'Test Brand',
                'model': 'Test Model'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'sensor.energy_consumption',
            'state': '1234.5',
            'attributes': {
                'friendly_name': 'Energy Consumption',
                'device_class': 'energy',
                'unit_of_measurement': 'kWh',
                'state_class': 'total'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'sensor.power_consumption',
            'state': '1500',
            'attributes': {
                'friendly_name': 'Power Consumption',
                'device_class': 'power',
                'unit_of_measurement': 'W'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'script.test_script',
            'state': 'off',
            'attributes': {
                'friendly_name': 'Test Script',
                'mode': 'single'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'input_boolean.test_helper',
            'state': 'on',
            'attributes': {
                'friendly_name': 'Test Helper'
            },
            'last_updated': '2024-01-01T12:00:00Z'
        },
        {
            'entity_id': 'sensor.unavailable_sensor',
            'state': 'unavailable',
            'attributes': {
                'friendly_name': 'Unavailable Sensor'
            },
            'last_updated': '2024-01-01T10:00:00Z'
        }
    ]


@pytest.fixture
def mock_services_response():
    """Mock /api/services response"""
    return {
        'light': {
            'turn_on': {
                'description': 'Turn on a light',
                'fields': {
                    'entity_id': {
                        'description': 'Entity ID',
                        'required': True,
                        'example': 'light.living_room'
                    },
                    'brightness': {
                        'description': 'Brightness level',
                        'required': False,
                        'example': 255
                    }
                }
            },
            'turn_off': {
                'description': 'Turn off a light',
                'fields': {
                    'entity_id': {
                        'description': 'Entity ID',
                        'required': True
                    }
                }
            }
        },
        'switch': {
            'turn_on': {
                'description': 'Turn on a switch',
                'fields': {
                    'entity_id': {
                        'description': 'Entity ID',
                        'required': True
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_events_response():
    """Mock /api/events response"""
    return [
        {'event': 'state_changed', 'listener_count': 15},
        {'event': 'call_service', 'listener_count': 8},
        {'event': 'automation_triggered', 'listener_count': 5}
    ]


@pytest.fixture
def mock_logbook_response():
    """Mock /api/logbook response"""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    return [
        {
            'when': (now - timedelta(minutes=10)).isoformat(),
            'name': 'Light turned on',
            'entity_id': 'light.living_room',
            'state': 'on',
            'domain': 'light'
        },
        {
            'when': (now - timedelta(minutes=5)).isoformat(),
            'name': 'Automation triggered',
            'entity_id': 'automation.test',
            'state': 'triggered',
            'domain': 'automation'
        }
    ]


@pytest.fixture
def mock_integrations_response():
    """Mock /api/config/config_entries/entry response"""
    return [
        {
            'title': 'MQTT',
            'domain': 'mqtt',
            'state': 'loaded',
            'entry_id': 'mqtt_123',
            'source': 'user'
        },
        {
            'title': 'Zigbee',
            'domain': 'zha',
            'state': 'loaded',
            'entry_id': 'zha_456',
            'source': 'user'
        }
    ]


@pytest.fixture
def mock_api_request(monkeypatch, mock_states_response, mock_services_response,
                     mock_events_response, mock_logbook_response, mock_integrations_response):
    """Mock make_api_request function for both old and new code"""
    def mock_request(url, token, method='GET', data=None):
        if '/api/states' in url:
            return mock_states_response
        elif '/api/services' in url:
            return mock_services_response
        elif '/api/events' in url:
            return mock_events_response
        elif '/api/logbook' in url:
            return mock_logbook_response
        elif '/api/config/config_entries/entry' in url:
            return mock_integrations_response
        elif '/api/history/period' in url:
            # Return empty list for history
            return []
        return []

    # Patch hactl core API module
    monkeypatch.setattr('hactl.core.api.make_api_request', mock_request)

    # Patch all handler modules that import make_api_request (from hactl.core)
    handler_modules = [
        'hactl.handlers.devices',
        'hactl.handlers.states',
        'hactl.handlers.sensors',
        'hactl.handlers.sensors_by_type',
        'hactl.handlers.integrations',
        'hactl.handlers.services',
        'hactl.handlers.dashboards',
        'hactl.handlers.automations_scripts_helpers',
        'hactl.handlers.actions',
        'hactl.handlers.activity',
        'hactl.handlers.assist',
        'hactl.handlers.calendars',
        'hactl.handlers.cameras',
        'hactl.handlers.energy',
        'hactl.handlers.error_log',
        'hactl.handlers.events',
        'hactl.handlers.hacs',
        'hactl.handlers.history',
        'hactl.handlers.home_structure',
        'hactl.handlers.media_players',
        'hactl.handlers.notifications',
        'hactl.handlers.persons_zones',
        'hactl.handlers.scenes',
        'hactl.handlers.statistics',
        'hactl.handlers.templates',
        'hactl.handlers.todos',
        'hactl.handlers.battery_monitor',
        'hactl.handlers.memory_mgmt',
        'hactl.handlers.dashboard_ops',
        'hactl.handlers.helper_ops',
    ]

    for module in handler_modules:
        try:
            monkeypatch.setattr(f'{module}.make_api_request', mock_request)
        except (ImportError, AttributeError):
            # Module doesn't exist or doesn't import make_api_request
            pass
