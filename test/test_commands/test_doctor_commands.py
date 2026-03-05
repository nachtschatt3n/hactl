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
def mock_doctor_api(monkeypatch, mock_states_response, mock_config_response,
                    mock_check_config_response, mock_error_log_response):
    """Mock all API calls needed by doctor command."""
    def mock_request(url, token, method='GET', data=None):
        if url.endswith('/api/'):
            return {'message': 'API running.'}
        elif '/api/states' in url:
            return mock_states_response
        elif '/api/config/core/check_config' in url:
            return mock_check_config_response
        elif '/api/error_log' in url:
            return mock_error_log_response
        elif '/api/config' in url:
            return mock_config_response
        return {}

    monkeypatch.setattr('hactl.core.api.make_api_request', mock_request)
    monkeypatch.setattr('hactl.handlers.doctor.make_api_request', mock_request)


def _make_doctor_api(monkeypatch, states, mock_config_response,
                     mock_check_config_response, mock_error_log_response):
    """Helper to set up doctor API mocks with custom states."""
    def mock_request(url, token, method='GET', data=None):
        if url.endswith('/api/'):
            return {'message': 'API running.'}
        elif '/api/states' in url:
            return states
        elif '/api/config/core/check_config' in url:
            return mock_check_config_response
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

    def test_check_integrations(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'integrations'])

        assert result.exit_code == 0
        assert 'Integration Status' in result.output

    def test_check_automations(self, mock_env_vars, mock_doctor_api):
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--check', 'automations'])

        assert result.exit_code == 0
        assert 'Automation Health' in result.output

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


class TestDoctorIntegrationStatus:
    """Test integration status check with smart filtering"""

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
        result = runner.invoke(cli, ['doctor', '--check', 'integrations', '--format', 'json'])

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
        result = runner.invoke(cli, ['doctor', '--check', 'integrations', '--format', 'json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        findings = data['checks'][0]['findings']
        warn_findings = [f for f in findings if f['status'] == 'warning']
        assert len(warn_findings) == 1
        assert '1/3' in warn_findings[0]['message']
        assert '33%' in warn_findings[0]['message']


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
