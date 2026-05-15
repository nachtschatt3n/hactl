"""
Tests for hactl doctor command using Click's CliRunner
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from click.testing import CliRunner
from hactl.cli import cli


@pytest.fixture
def mock_config_response():
    """Mock /api/config response"""
    return {
        'version': '2025.2.1',
        'location_name': 'Home',
        'time_zone': 'Europe/Oslo',
        'components': ['light', 'sensor', 'automation', 'mqtt'],
    }


@pytest.fixture
def mock_check_config_response():
    """Mock /api/config/core/check_config response"""
    return {'result': 'valid', 'errors': None}


@pytest.fixture
def mock_error_log_response():
    """Mock /api/error_log response"""
    return (
        "2025-01-01 12:00:00 ERROR homeassistant.components.shelly: Connection failed\n"
        "2025-01-01 12:01:00 ERROR homeassistant.components.shelly: Timeout\n"
        "2025-01-01 12:02:00 ERROR homeassistant.components.mqtt: Disconnected\n"
        "2025-01-01 12:03:00 WARNING homeassistant.core: Slow setup\n"
    )


@pytest.fixture
def mock_config_entries_response():
    """Mock /api/config/config_entries/entry response — all loaded by default."""
    return [
        {'entry_id': 'a1', 'domain': 'mqtt', 'title': 'MQTT', 'state': 'loaded',
         'source': 'user', 'disabled_by': None, 'reason': None},
        {'entry_id': 'a2', 'domain': 'zha', 'title': 'Zigbee', 'state': 'loaded',
         'source': 'user', 'disabled_by': None, 'reason': None},
    ]


@pytest.fixture
def mock_doctor_api(monkeypatch, mock_states_response, mock_config_response,
                    mock_check_config_response, mock_error_log_response,
                    mock_config_entries_response):
    """Mock all API calls needed by doctor command."""
    def mock_request(url, token, method='GET', data=None):
        if url.endswith('/api/'):
            return {'message': 'API running.'}
        elif '/api/states' in url:
            return mock_states_response
        elif '/api/config/core/check_config' in url:
            return mock_check_config_response
        elif '/api/config/config_entries/entry' in url:
            return mock_config_entries_response
        elif '/api/error_log' in url:
            return mock_error_log_response
        elif '/api/config' in url:
            return mock_config_response
        return {}

    monkeypatch.setattr('hactl.core.api.make_api_request', mock_request)
    monkeypatch.setattr('hactl.handlers.doctor.make_api_request', mock_request)


def _make_doctor_api(monkeypatch, states, mock_config_response,
                     mock_check_config_response, mock_error_log_response,
                     config_entries=None):
    """Helper to set up doctor API mocks with custom states."""
    entries = config_entries if config_entries is not None else []

    def mock_request(url, token, method='GET', data=None):
        if url.endswith('/api/'):
            return {'message': 'API running.'}
        elif '/api/states' in url:
            return states
        elif '/api/config/core/check_config' in url:
            return mock_check_config_response
        elif '/api/config/config_entries/entry' in url:
            return entries
        elif '/api/error_log' in url:
            return mock_error_log_response
        elif '/api/config' in url:
            return mock_config_response
        return {}

    monkeypatch.setattr('hactl.core.api.make_api_request', mock_request)
    monkeypatch.setattr('hactl.handlers.doctor.make_api_request', mock_request)


class TestDoctorFull:
    """Test hactl doctor full report"""

    def test_doctor_table(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor'])

        assert result.exit_code == 0
        assert 'Home Assistant Health Report' in result.output
        assert 'API Connectivity' in result.output
        assert 'Summary' in result.output
        assert 'Overall Health' in result.output

    def test_doctor_json(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'checks' in data
        assert 'summary' in data
        assert 'instance' in data
        assert data['summary']['overall'] in ('HEALTHY', 'WARNING', 'CRITICAL')
        assert 'actionable' in data['summary']

    def test_doctor_shows_version(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor'])

        assert result.exit_code == 0
        assert '2025.2.1' in result.output

    def test_doctor_shows_actionable_count(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor'])

        assert result.exit_code == 0
        assert 'Actionable:' in result.output


class TestDoctorSingleCheck:
    """Test hactl doctor --check <name>"""

    def test_check_api(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'api'])

        assert result.exit_code == 0
        assert 'API Connectivity' in result.output

    def test_check_unavailable(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable'])

        assert result.exit_code == 0
        assert 'Unavailable Entities' in result.output
        # sensor.unavailable_sensor should appear in truly unavailable grouping
        assert 'Truly unavailable' in result.output

    def test_check_batteries(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'batteries'])

        assert result.exit_code == 0
        assert 'Low Battery Devices' in result.output

    def test_check_error_log(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'error_log'])

        assert result.exit_code == 0
        assert 'Error Log' in result.output

    def test_check_config(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config'])

        assert result.exit_code == 0
        assert 'Configuration' in result.output

    def test_check_stale(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'stale'])

        assert result.exit_code == 0
        assert 'Stale Entities' in result.output

    def test_check_version(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'version'])

        assert result.exit_code == 0
        assert 'Version' in result.output

    def test_check_entity_availability(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'entity_availability'])

        assert result.exit_code == 0
        assert 'Entity Availability by Domain' in result.output

    def test_check_config_entries(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config_entries'])

        assert result.exit_code == 0
        assert 'Integrations' in result.output

    def test_check_automations(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'automations'])

        assert result.exit_code == 0
        assert 'Automation Health' in result.output

    def test_check_zombie_devices(self, mock_env_vars, mock_doctor_api,
                                  monkeypatch):
        # zombie_devices needs a websocket — mock it to return empty registries.
        monkeypatch.setattr(
            'hactl.handlers.doctor._fetch_registries',
            lambda url, token: ([], []))
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'zombie_devices'])

        assert result.exit_code == 0
        assert 'Zombie Devices' in result.output

    def test_check_unknown(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'nonexistent'])

        assert result.exit_code != 0
        assert 'Unknown check' in result.output


class TestDoctorUnavailableDetection:
    """Test that unavailable entities are properly detected and categorized"""

    def test_detects_unavailable_sensor(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        messages = [f['message'] for f in findings]
        # Should appear in "Truly unavailable" grouping
        assert any('Truly unavailable' in m for m in messages)

    def test_expected_unknown_classified_as_info(self, mock_env_vars, monkeypatch,
                                                  mock_config_response, mock_check_config_response,
                                                  mock_error_log_response):
        """Button/event/scene entities in 'unknown' state should be INFO, not WARNING."""
        states = [
            {'entity_id': 'button.restart_device', 'state': 'unknown',
             'attributes': {'friendly_name': 'Restart Device'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'event.doorbell_press', 'state': 'unknown',
             'attributes': {'friendly_name': 'Doorbell Press'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'scene.movie_night', 'state': 'unknown',
             'attributes': {'friendly_name': 'Movie Night'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.healthy', 'state': '42',
             'attributes': {'friendly_name': 'Healthy'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        # Should have an INFO finding about action entities
        info_findings = [f for f in findings if f['status'] == 'info']
        assert any('action entities' in f['message'] for f in info_findings)
        # Should NOT have any warnings
        warn_findings = [f for f in findings if f['status'] == 'warning']
        assert len(warn_findings) == 0

    def test_mobile_devices_classified_as_info(self, mock_env_vars, monkeypatch,
                                                mock_config_response, mock_check_config_response,
                                                mock_error_log_response):
        """Mobile device entities that are unavailable should be INFO."""
        states = [
            {'entity_id': 'sensor.johns_iphone_battery', 'state': 'unavailable',
             'attributes': {'friendly_name': "John's iPhone Battery"},
             'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'device_tracker.janes_ipad', 'state': 'unavailable',
             'attributes': {'friendly_name': "Jane's iPad"},
             'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.macbook_pro_battery', 'state': 'unavailable',
             'attributes': {'friendly_name': "MacBook Pro Battery"},
             'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        info_findings = [f for f in findings if f['status'] == 'info']
        assert any('mobile device' in f['message'] for f in info_findings)
        warn_findings = [f for f in findings if f['status'] == 'warning']
        assert len(warn_findings) == 0

    def test_appliances_classified_as_info(self, mock_env_vars, monkeypatch,
                                           mock_config_response, mock_check_config_response,
                                           mock_error_log_response):
        """Appliance entities that are unavailable should be INFO."""
        states = [
            {'entity_id': 'sensor.washing_machine_status', 'state': 'unavailable',
             'attributes': {'friendly_name': 'Washing Machine'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.tumble_dryer_power', 'state': 'unavailable',
             'attributes': {'friendly_name': 'Tumble Dryer'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        info_findings = [f for f in findings if f['status'] == 'info']
        assert any('appliance' in f['message'] for f in info_findings)
        warn_findings = [f for f in findings if f['status'] == 'warning']
        assert len(warn_findings) == 0

    def test_truly_unavailable_is_warning(self, mock_env_vars, monkeypatch,
                                          mock_config_response, mock_check_config_response,
                                          mock_error_log_response):
        """Entities that are truly unavailable should be WARNING with grouping."""
        states = [
            {'entity_id': 'sensor.shelly_kitchen_power', 'state': 'unavailable',
             'attributes': {'friendly_name': 'Shelly Kitchen Power'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.shelly_kitchen_temp', 'state': 'unavailable',
             'attributes': {'friendly_name': 'Shelly Kitchen Temp'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.zigbee_motion', 'state': 'unavailable',
             'attributes': {'friendly_name': 'Zigbee Motion'},
             'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        warn_findings = [f for f in findings if f['status'] == 'warning']
        assert len(warn_findings) > 0
        assert any('Truly unavailable' in f['message'] for f in warn_findings)
        assert any('3 entities' in f['message'] for f in warn_findings)

    def test_mixed_categories(self, mock_env_vars, monkeypatch,
                              mock_config_response, mock_check_config_response,
                              mock_error_log_response):
        """Test a mix of expected unknown, mobile, appliance, and truly unavailable."""
        states = [
            {'entity_id': 'button.restart', 'state': 'unknown',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.johns_iphone_battery', 'state': 'unavailable',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.washing_machine_power', 'state': 'unavailable',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.shelly_offline', 'state': 'unavailable',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.healthy_one', 'state': '10',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        messages = ' '.join(f['message'] for f in findings)
        assert 'action entities' in messages
        assert 'mobile device' in messages
        assert 'appliance' in messages
        assert 'Truly unavailable' in messages
        assert '1 entities healthy' in messages

    def test_all_healthy_no_warnings(self, mock_env_vars, monkeypatch,
                                     mock_config_response, mock_check_config_response,
                                     mock_error_log_response):
        """When all entities are healthy, no warnings should appear."""
        states = [
            {'entity_id': 'sensor.temp', 'state': '21',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        assert all(f['status'] in ('ok', 'info') for f in findings)
        assert any('1 entities healthy' in f['message'] for f in findings)


class TestDoctorEntityAvailability:
    """Test entity-availability-by-domain check with smart filtering"""

    def test_expected_unknowns_excluded(self, mock_env_vars, monkeypatch,
                                        mock_config_response, mock_check_config_response,
                                        mock_error_log_response):
        """Button domain with all 'unknown' entities should not show as warning."""
        states = [
            {'entity_id': 'button.restart_a', 'state': 'unknown',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'button.restart_b', 'state': 'unknown',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.temp', 'state': '21',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'entity_availability', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        # Button domain should not appear as warning
        warn_messages = [f['message'] for f in findings if f['status'] == 'warning']
        assert not any('button' in m for m in warn_messages)

    def test_shows_percentage(self, mock_env_vars, monkeypatch,
                              mock_config_response, mock_check_config_response,
                              mock_error_log_response):
        """Integration status should show count/total and percentage."""
        states = [
            {'entity_id': 'sensor.a', 'state': 'unavailable',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.b', 'state': '21',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
            {'entity_id': 'sensor.c', 'state': '22',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'entity_availability', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        warn_findings = [f for f in findings if f['status'] == 'warning']
        assert len(warn_findings) == 1
        assert '1/3' in warn_findings[0]['message']
        assert '33%' in warn_findings[0]['message']


class TestDoctorConfigEntries:
    """Test config-entry (integration setup) check."""

    def _entries_api(self, monkeypatch, entries, mock_config_response,
                     mock_check_config_response, mock_error_log_response):
        # No state-driven checks needed; provide an empty states list.
        _make_doctor_api(monkeypatch, [], mock_config_response,
                         mock_check_config_response, mock_error_log_response,
                         config_entries=entries)

    def test_all_loaded_no_findings(self, mock_env_vars, monkeypatch,
                                    mock_config_response, mock_check_config_response,
                                    mock_error_log_response):
        entries = [
            {'entry_id': '1', 'domain': 'mqtt', 'title': 'MQTT', 'state': 'loaded',
             'source': 'user', 'disabled_by': None, 'reason': None},
        ]
        self._entries_api(monkeypatch, entries, mock_config_response,
                          mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config_entries', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        assert all(f['status'] == 'ok' for f in findings)
        assert any('1 integrations loaded' in f['message'] for f in findings)

    def test_setup_error_is_critical(self, mock_env_vars, monkeypatch,
                                     mock_config_response, mock_check_config_response,
                                     mock_error_log_response):
        entries = [
            {'entry_id': '1', 'domain': 'smartthings', 'title': 'SmartThings',
             'state': 'setup_error', 'source': 'user', 'disabled_by': None,
             'reason': 'Token expired'},
        ]
        self._entries_api(monkeypatch, entries, mock_config_response,
                          mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config_entries', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        crit = [f for f in findings if f['status'] == 'critical']
        assert len(crit) == 1
        assert 'smartthings' in crit[0]['message']
        assert 'setup_error' in crit[0]['message']
        assert 'Token expired' in crit[0]['message']

    def test_setup_retry_is_warning(self, mock_env_vars, monkeypatch,
                                    mock_config_response, mock_check_config_response,
                                    mock_error_log_response):
        entries = [
            {'entry_id': '1', 'domain': 'music_assistant',
             'title': 'Music Assistant', 'state': 'setup_retry',
             'source': 'user', 'disabled_by': None,
             'reason': 'Failed to connect to music assistant server `http://192.168.55.25`'},
        ]
        self._entries_api(monkeypatch, entries, mock_config_response,
                          mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config_entries', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        warns = [f for f in findings if f['status'] == 'warning']
        assert len(warns) == 1
        assert 'music_assistant' in warns[0]['message']
        assert 'setup_retry' in warns[0]['message']

    def test_disabled_by_is_ignored(self, mock_env_vars, monkeypatch,
                                    mock_config_response, mock_check_config_response,
                                    mock_error_log_response):
        entries = [
            {'entry_id': '1', 'domain': 'flichub', 'title': 'flichub',
             'state': 'not_loaded', 'source': 'user', 'disabled_by': 'user',
             'reason': None},
            {'entry_id': '2', 'domain': 'mqtt', 'title': 'MQTT',
             'state': 'loaded', 'source': 'user', 'disabled_by': None,
             'reason': None},
        ]
        self._entries_api(monkeypatch, entries, mock_config_response,
                          mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config_entries', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        # No critical/warning findings for the user-disabled entry.
        assert not any(f['status'] in ('critical', 'warning') for f in findings)

    def test_source_ignore_is_ignored(self, mock_env_vars, monkeypatch,
                                      mock_config_response, mock_check_config_response,
                                      mock_error_log_response):
        entries = [
            {'entry_id': '1', 'domain': 'zha', 'title': 'SLZB-06P10',
             'state': 'not_loaded', 'source': 'ignore', 'disabled_by': None,
             'reason': None},
            {'entry_id': '2', 'domain': 'xbox', 'title': 'xbox',
             'state': 'not_loaded', 'source': 'ignore', 'disabled_by': None,
             'reason': None},
        ]
        self._entries_api(monkeypatch, entries, mock_config_response,
                          mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config_entries', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        assert not any(f['status'] in ('critical', 'warning') for f in findings)

    def test_reason_passthrough(self, mock_env_vars, monkeypatch,
                                mock_config_response, mock_check_config_response,
                                mock_error_log_response):
        """Reason field should appear in output verbatim after em-dash."""
        reason = 'Failed to connect to music assistant server `http://192.168.55.25`'
        entries = [
            {'entry_id': '1', 'domain': 'music_assistant',
             'title': 'Music Assistant Home', 'state': 'setup_retry',
             'source': 'user', 'disabled_by': None, 'reason': reason},
        ]
        self._entries_api(monkeypatch, entries, mock_config_response,
                          mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config_entries', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        msgs = [f['message'] for f in findings]
        assert any(reason in m for m in msgs)
        assert any('—' in m for m in msgs)

    def test_migration_error_is_critical(self, mock_env_vars, monkeypatch,
                                         mock_config_response, mock_check_config_response,
                                         mock_error_log_response):
        entries = [
            {'entry_id': '1', 'domain': 'foo', 'title': 'Foo',
             'state': 'migration_error', 'source': 'user', 'disabled_by': None,
             'reason': None},
        ]
        self._entries_api(monkeypatch, entries, mock_config_response,
                          mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'config_entries', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        assert any(f['status'] == 'critical' for f in findings)


class TestDoctorBatteryDetection:
    """Test battery detection with custom states"""

    def test_critical_battery(self, mock_env_vars, monkeypatch, mock_config_response,
                              mock_check_config_response, mock_error_log_response):
        states = [
            {
                'entity_id': 'sensor.door_battery',
                'state': '8',
                'attributes': {'device_class': 'battery', 'friendly_name': 'Door Battery'},
                'last_changed': datetime.now(timezone.utc).isoformat(),
            }
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'batteries', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        assert any(f['status'] == 'critical' for f in findings)
        assert any('8%' in f['message'] for f in findings)


class TestDoctorStaleDetection:
    """Test stale entity detection"""

    def test_stale_entity_detected(self, mock_env_vars, monkeypatch, mock_config_response,
                                   mock_check_config_response, mock_error_log_response):
        old_time = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        states = [
            {
                'entity_id': 'sensor.garage_temp',
                'state': '15.2',
                'attributes': {'friendly_name': 'Garage Temp'},
                'last_changed': old_time,
                'last_updated': old_time,
            }
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'stale', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        assert any('sensor.garage_temp' in f['message'] for f in findings)
        assert any('3 days ago' in f['message'] for f in findings)

    def test_static_domains_excluded(self, mock_env_vars, monkeypatch, mock_config_response,
                                     mock_check_config_response, mock_error_log_response):
        old_time = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        states = [
            {
                'entity_id': 'zone.home',
                'state': 'zoning',
                'attributes': {'friendly_name': 'Home'},
                'last_changed': old_time,
            }
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'stale', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        assert all('zone.home' not in f['message'] for f in findings)


class TestDoctorSummary:
    """Test that summary reflects actionable findings"""

    def test_info_only_shows_healthy(self, mock_env_vars, monkeypatch,
                                     mock_config_response, mock_check_config_response,
                                     mock_error_log_response):
        """When only INFO and OK findings exist, overall should be HEALTHY."""
        # All entities are expected-unknown buttons — only INFO findings
        states = [
            {'entity_id': 'button.restart', 'state': 'unknown',
             'attributes': {}, 'last_changed': datetime.now(timezone.utc).isoformat()},
        ]
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)

        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'unavailable', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['summary']['overall'] == 'HEALTHY'
        assert data['summary']['actionable'] == 0


class TestDoctorHelp:
    """Test help output"""

    def test_doctor_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--help'])

        assert result.exit_code == 0
        assert 'health checks' in result.output.lower()
        assert '--format' in result.output
        assert '--check' in result.output

    def test_doctor_in_main_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])

        assert result.exit_code == 0
        assert 'doctor' in result.output


class TestDoctorZombieDevices:
    """Test zombie-device check (orphan / stalled / disabled / restored)."""

    def _run(self, monkeypatch, devices, entities, states,
             mock_config_response, mock_check_config_response,
             mock_error_log_response):
        _make_doctor_api(monkeypatch, states, mock_config_response,
                         mock_check_config_response, mock_error_log_response)
        monkeypatch.setattr(
            'hactl.handlers.doctor._fetch_registries',
            lambda url, token: (devices, entities))
        runner = CliRunner()
        result = runner.invoke(
            cli, ['doctor', '--check', 'zombie_devices', '--format', 'json'])
        assert result.exit_code == 0
        return json.loads(result.output)

    def test_no_zombies_is_ok(self, mock_env_vars, monkeypatch,
                              mock_config_response, mock_check_config_response,
                              mock_error_log_response):
        # 1 device with 1 healthy enabled entity, no restored states.
        devices = [{'id': 'dev1', 'name': 'Healthy Device',
                    'manufacturer': 'Acme', 'config_entries': ['ce1'],
                    'disabled_by': None}]
        entities = [{'entity_id': 'sensor.healthy', 'device_id': 'dev1',
                     'disabled_by': None}]
        states = [{'entity_id': 'sensor.healthy', 'state': '42',
                   'attributes': {}, 'last_changed': '2025-01-01T00:00:00Z'}]
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert all(f['status'] == 'ok' for f in findings)
        assert any('No zombie' in f['message'] for f in findings)

    def test_orphan_device_below_threshold_is_info(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        # 1 orphan device (no enabled entities).
        devices = [{'id': 'dev1', 'name': 'Orphan',
                    'manufacturer': 'Acme', 'config_entries': ['ce1'],
                    'disabled_by': None}]
        entities = []
        states = []
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert any('Orphan devices' in f['message'] and '1' in f['message']
                   for f in findings)
        # 1 orphan is well below the 25 threshold → INFO not WARNING.
        warns = [f for f in findings if f['status'] == 'warning']
        assert len(warns) == 0

    def test_orphan_devices_above_threshold_is_warning(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        # 30 orphan devices (above the 25 default threshold).
        devices = [{'id': f'dev{i}', 'name': f'Orphan {i}',
                    'manufacturer': 'Acme', 'config_entries': ['ce1'],
                    'disabled_by': None} for i in range(30)]
        entities = []
        states = []
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        warn = [f for f in findings if f['status'] == 'warning'
                and 'Orphan devices' in f['message']]
        assert len(warn) == 1
        assert '30' in warn[0]['message']

    def test_top_n_truncation(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        # 50 orphans → only 5 example labels shown + a "and N more" line.
        devices = [{'id': f'dev{i:02d}', 'name': f'Orphan{i}',
                    'manufacturer': 'Acme', 'config_entries': ['ce1'],
                    'disabled_by': None} for i in range(50)]
        entities = []
        states = []
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        # Count info findings whose message starts with two leading spaces
        # (those are the per-device example lines).
        example_lines = [f for f in findings
                         if f['message'].startswith('  Orphan')]
        assert len(example_lines) == 5
        assert any('and 45 more' in f['message'] for f in findings)

    def test_stalled_device_detected(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        # Device has 2 enabled entities, both currently unavailable.
        devices = [{'id': 'dev1', 'name': 'Dead Sensor',
                    'manufacturer': 'Aqara', 'config_entries': ['ce1'],
                    'disabled_by': None}]
        entities = [
            {'entity_id': 'sensor.dead_temp', 'device_id': 'dev1',
             'disabled_by': None},
            {'entity_id': 'sensor.dead_humidity', 'device_id': 'dev1',
             'disabled_by': None},
        ]
        states = [
            {'entity_id': 'sensor.dead_temp', 'state': 'unavailable',
             'attributes': {}, 'last_changed': '2025-01-01T00:00:00Z'},
            {'entity_id': 'sensor.dead_humidity', 'state': 'unavailable',
             'attributes': {}, 'last_changed': '2025-01-01T00:00:00Z'},
        ]
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert any('Stalled devices' in f['message'] and '1' in f['message']
                   for f in findings)
        # Device label should appear in top-N example.
        assert any('Dead Sensor' in f['message'] for f in findings)

    def test_stalled_skipped_when_one_entity_alive(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        # One unavailable, one alive → NOT stalled.
        devices = [{'id': 'dev1', 'name': 'Mixed',
                    'manufacturer': 'Acme', 'config_entries': ['ce1'],
                    'disabled_by': None}]
        entities = [
            {'entity_id': 'sensor.mixed_a', 'device_id': 'dev1',
             'disabled_by': None},
            {'entity_id': 'sensor.mixed_b', 'device_id': 'dev1',
             'disabled_by': None},
        ]
        states = [
            {'entity_id': 'sensor.mixed_a', 'state': 'unavailable',
             'attributes': {}, 'last_changed': '2025-01-01T00:00:00Z'},
            {'entity_id': 'sensor.mixed_b', 'state': '42',
             'attributes': {}, 'last_changed': '2025-01-01T00:00:00Z'},
        ]
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert not any('Stalled devices' in f['message'] for f in findings)

    def test_disabled_device_detected(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        devices = [{'id': 'dev1', 'name': 'Flic',
                    'manufacturer': 'Flic', 'config_entries': ['ce1'],
                    'disabled_by': 'user'}]
        entities = []
        states = []
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert any('Disabled devices' in f['message'] for f in findings)
        # Disabled is INFO regardless of count (user-controlled state).
        warns = [f for f in findings if f['status'] == 'warning']
        assert all('Disabled devices' not in f['message'] for f in warns)

    def test_disabled_device_not_counted_as_orphan(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        # Disabled device with no enabled entities → counted as disabled,
        # NOT orphan (we want to surface the actionable category).
        devices = [{'id': 'dev1', 'name': 'Flic',
                    'manufacturer': 'Flic', 'config_entries': ['ce1'],
                    'disabled_by': 'user'}]
        entities = []
        states = []
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert not any('Orphan devices' in f['message'] for f in findings)

    def test_restored_entity_detected(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        devices = []
        entities = []
        states = [
            {'entity_id': 'device_tracker.old_phone',
             'state': 'unavailable',
             'attributes': {'restored': True},
             'last_changed': '2025-01-01T00:00:00Z'},
        ]
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert any('Restored entities' in f['message'] and '1' in f['message']
                   for f in findings)
        assert any('device_tracker.old_phone' in f['message']
                   for f in findings)

    def test_restored_entities_above_threshold_is_warning(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        devices = []
        entities = []
        states = [
            {'entity_id': f'sensor.restored_{i}',
             'state': 'unavailable',
             'attributes': {'restored': True},
             'last_changed': '2025-01-01T00:00:00Z'}
            for i in range(60)
        ]
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        warn = [f for f in findings if f['status'] == 'warning'
                and 'Restored entities' in f['message']]
        assert len(warn) == 1
        assert '60' in warn[0]['message']

    def test_disabled_entities_make_device_orphan(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        # Device has entities but all are disabled_by set → orphan.
        devices = [{'id': 'dev1', 'name': 'AllDisabled',
                    'manufacturer': 'Acme', 'config_entries': ['ce1'],
                    'disabled_by': None}]
        entities = [
            {'entity_id': 'sensor.x', 'device_id': 'dev1',
             'disabled_by': 'user'},
            {'entity_id': 'sensor.y', 'device_id': 'dev1',
             'disabled_by': 'integration'},
        ]
        states = []
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert any('Orphan devices' in f['message'] for f in findings)

    def test_websocket_failure_emits_warning(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        # Simulate websocket failure → returns None.
        _make_doctor_api(monkeypatch, [], mock_config_response,
                         mock_check_config_response, mock_error_log_response)
        monkeypatch.setattr(
            'hactl.handlers.doctor._fetch_registries',
            lambda url, token: None)
        runner = CliRunner()
        result = runner.invoke(
            cli, ['doctor', '--check', 'zombie_devices', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        assert any(f['status'] == 'warning'
                   and 'websocket' in f['message'].lower()
                   for f in findings)

    def test_total_summary_line_present(
            self, mock_env_vars, monkeypatch,
            mock_config_response, mock_check_config_response,
            mock_error_log_response):
        devices = [
            {'id': 'dev1', 'name': 'Orphan', 'manufacturer': 'Acme',
             'config_entries': ['ce1'], 'disabled_by': None},
        ]
        entities = []
        states = [
            {'entity_id': 'sensor.r', 'state': 'unavailable',
             'attributes': {'restored': True},
             'last_changed': '2025-01-01T00:00:00Z'},
        ]
        data = self._run(monkeypatch, devices, entities, states,
                         mock_config_response, mock_check_config_response,
                         mock_error_log_response)
        findings = data['checks'][0]['findings']
        assert any('Total zombie items' in f['message'] for f in findings)
