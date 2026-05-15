"""
Tests for the HAGHS-parity `unavailable_entity` zombie category and
the live-state delete safety predicate.

Covers:
  - TestUnavailableEntityDetection
  - TestUnavailableEntityGracePeriod
  - TestDeleteSafetyLiveState
  - TestStateOnlyUnavailableFilter
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from hactl.cli import cli
from hactl.handlers import deletions
from hactl.handlers.doctor import (
    ZOMBIE_UNAVAILABLE_GRACE_SECONDS,
    classify_zombies,
)


def _ts(now, seconds_ago):
    """Return an ISO timestamp `seconds_ago` seconds before `now`."""
    return (now - timedelta(seconds=seconds_ago)).isoformat()


# ---------------------------------------------------------------------------
# TestUnavailableEntityDetection
# ---------------------------------------------------------------------------

class TestUnavailableEntityDetection:
    def setup_method(self):
        self.now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
        # Helpful constant: well past the 15min grace window.
        self.STALE = ZOMBIE_UNAVAILABLE_GRACE_SECONDS + 600

    def _classify(self, states, entities=None, devices=None,
                  ignore_label=None):
        return classify_zombies(
            devices or [], entities or [], states,
            ignore_label=ignore_label, now=self.now)

    def test_unavailable_sensor_caught(self):
        states = [{
            'entity_id': 'sensor.broken_temp',
            'state': 'unavailable',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states)
        assert len(out['unavailable_entities']) == 1
        assert out['unavailable_entities'][0][0]['entity_id'] == 'sensor.broken_temp'

    def test_unknown_state_caught(self):
        states = [{
            'entity_id': 'binary_sensor.contact',
            'state': 'unknown',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states)
        assert len(out['unavailable_entities']) == 1

    def test_live_state_skipped(self):
        states = [{
            'entity_id': 'sensor.temp',
            'state': '21.5',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states)
        assert out['unavailable_entities'] == []

    def test_non_whitelisted_domain_skipped(self):
        # `automation` is not in ZOMBIE_UNAVAILABLE_DOMAINS.
        states = [{
            'entity_id': 'automation.morning_routine',
            'state': 'unavailable',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states)
        assert out['unavailable_entities'] == []

    def test_button_domain_skipped(self):
        # buttons are naturally `unknown` between presses; not a zombie.
        states = [{
            'entity_id': 'button.reboot_router',
            'state': 'unknown',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states)
        assert out['unavailable_entities'] == []

    def test_integration_health_self_reference_skipped(self):
        states = [{
            'entity_id': 'sensor.haghs_integration_health',
            'state': 'unknown',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states)
        assert out['unavailable_entities'] == []

    def test_ignore_label_on_entity(self):
        entities = [{
            'entity_id': 'sensor.muted',
            'platform': 'foo',
            'device_id': None,
            'labels': ['haghs_ignore'],
        }]
        states = [{
            'entity_id': 'sensor.muted',
            'state': 'unavailable',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states, entities=entities,
                             ignore_label='haghs_ignore')
        assert out['unavailable_entities'] == []

    def test_ignore_label_on_device(self):
        devices = [{
            'id': 'dev1',
            'name': 'Quiet Device',
            'labels': ['haghs_ignore'],
        }]
        entities = [{
            'entity_id': 'sensor.muted_via_device',
            'platform': 'foo',
            'device_id': 'dev1',
            'labels': [],
        }]
        states = [{
            'entity_id': 'sensor.muted_via_device',
            'state': 'unavailable',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states, entities=entities, devices=devices,
                             ignore_label='haghs_ignore')
        assert out['unavailable_entities'] == []

    def test_custom_ignore_label(self):
        entities = [{
            'entity_id': 'sensor.muted2',
            'platform': 'foo',
            'device_id': None,
            'labels': ['my_ignore'],
        }]
        states = [{
            'entity_id': 'sensor.muted2',
            'state': 'unavailable',
            'attributes': {},
            'last_changed': _ts(self.now, self.STALE),
        }]
        out = self._classify(states, entities=entities,
                             ignore_label='my_ignore')
        assert out['unavailable_entities'] == []
        # And without the matching label, it IS caught:
        out2 = self._classify(states, entities=entities,
                              ignore_label='something_else')
        assert len(out2['unavailable_entities']) == 1


# ---------------------------------------------------------------------------
# TestUnavailableEntityGracePeriod
# ---------------------------------------------------------------------------

class TestUnavailableEntityGracePeriod:
    def setup_method(self):
        self.now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)

    def test_just_under_grace_window_ignored(self):
        # 14:59 → still within the 15min grace; ignored.
        states = [{
            'entity_id': 'sensor.flapping',
            'state': 'unavailable',
            'attributes': {},
            'last_changed': _ts(self.now, ZOMBIE_UNAVAILABLE_GRACE_SECONDS - 60),
        }]
        out = classify_zombies([], [], states, now=self.now)
        assert out['unavailable_entities'] == []

    def test_just_over_grace_window_caught(self):
        # 15:01 → past the 15min grace; caught.
        states = [{
            'entity_id': 'sensor.stale',
            'state': 'unavailable',
            'attributes': {},
            'last_changed': _ts(self.now, ZOMBIE_UNAVAILABLE_GRACE_SECONDS + 60),
        }]
        out = classify_zombies([], [], states, now=self.now)
        assert len(out['unavailable_entities']) == 1

    def test_missing_last_changed_ignored(self):
        # No timestamp → can't compute age → don't risk a false positive.
        states = [{
            'entity_id': 'sensor.no_ts',
            'state': 'unavailable',
            'attributes': {},
        }]
        out = classify_zombies([], [], states, now=self.now)
        assert out['unavailable_entities'] == []


# ---------------------------------------------------------------------------
# Shared fixtures for delete-safety tests (mirrors test_delete_commands).
# ---------------------------------------------------------------------------

@pytest.fixture
def delete_registries():
    """Live-state-rich registry fixture for delete safety tests."""
    return {
        'devices': [
            {
                'id': 'dev_iphone',
                'name': "Andrea's iPhone 12 Pro",
                'name_by_user': None,
                'manufacturer': 'Apple',
                'model': 'iPhone',
                'area_id': None,
                'config_entries': ['ce_mobile'],
                'disabled_by': None,
                'labels': [],
            },
        ],
        'entities': [
            {
                'entity_id': 'sensor.andreas_iphone_12_pro_battery_level',
                'platform': 'mobile_app',
                'config_entry_id': 'ce_mobile',
                'device_id': 'dev_iphone',
                'disabled_by': None,
                'labels': [],
            },
            {
                'entity_id': 'sensor.dead_iphone_battery_level',
                'platform': 'mobile_app',
                'config_entry_id': 'ce_mobile',
                'device_id': 'dev_iphone',
                'disabled_by': None,
                'labels': [],
            },
        ],
        'areas': [],
        'config_entries': [
            {'entry_id': 'ce_mobile', 'domain': 'mobile_app',
             'state': 'loaded', 'source': 'user', 'title': 'Mobile App'},
        ],
        'states': [
            # The CRITICAL one — this is the iPhone-12-Pro mistake's victim.
            {'entity_id': 'sensor.andreas_iphone_12_pro_battery_level',
             'state': '100', 'attributes': {}},
            {'entity_id': 'sensor.dead_iphone_battery_level',
             'state': 'unavailable', 'attributes': {}},
        ],
        'ws_ok': True,
    }


@pytest.fixture
def patch_delete_env(monkeypatch, delete_registries, tmp_path):
    fake_ws = MagicMock()
    fake_ws.connect.return_value = None
    fake_ws.close.return_value = None
    fake_ws.call.return_value = None

    monkeypatch.setenv('HASS_URL', 'https://test-hass.example.com')
    monkeypatch.setenv('HASS_TOKEN', 'test_token_12345')
    monkeypatch.setattr(
        'hactl.handlers.deletions.load_config',
        lambda: ('https://test-hass.example.com', 'test_token_12345'))
    monkeypatch.setattr(
        'hactl.core.config.load_config',
        lambda: ('https://test-hass.example.com', 'test_token_12345'))
    monkeypatch.setattr(
        'hactl.handlers.deletions.fetch_registries',
        lambda *_a, **_kw: delete_registries)
    monkeypatch.setattr(
        'hactl.handlers.deletions.WebSocketClient',
        lambda *a, **kw: fake_ws)
    # No 7-day history activity by default — we only want the live-state
    # predicate to trip in these tests, not the existing recent-activity
    # one.
    monkeypatch.setattr(
        'hactl.handlers.deletions._has_recent_activity_for_entity',
        lambda *a, **kw: False)
    return {'fake_ws': fake_ws, 'registries': delete_registries}


# ---------------------------------------------------------------------------
# TestDeleteSafetyLiveState
# ---------------------------------------------------------------------------

class TestDeleteSafetyLiveState:
    def test_bulk_refuses_live_entity(self, patch_delete_env, tmp_path):
        ws = patch_delete_env['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        # Bulk delete: filter that catches BOTH the live and dead entity.
        # The live one must be hard-refused; the dead one is allowed.
        result = runner.invoke(cli, [
            'delete', 'entities', '--filter', 'platform=mobile_app',
            '--yes', '--audit', audit,
        ])
        # Should mention REFUSED for the live entity.
        assert 'REFUSED' in result.output
        assert 'sensor.andreas_iphone_12_pro_battery_level' in result.output
        assert "live state '100'" in result.output
        # The live entity must NOT have been deleted.
        for call in ws.call.call_args_list:
            args, kwargs = call.args, call.kwargs
            assert kwargs.get('entity_id') != \
                'sensor.andreas_iphone_12_pro_battery_level'

    def test_force_bypasses_live_state_predicate(self, patch_delete_env,
                                                 tmp_path, monkeypatch):
        # --force must let the dangerous delete through (audit still
        # written). We also have to bypass the existing recent-activity
        # predicate the same way --force already does.
        ws = patch_delete_env['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'entities', '--filter', 'platform=mobile_app',
            '--yes', '--force', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        deleted_eids = [c.kwargs.get('entity_id')
                        for c in ws.call.call_args_list
                        if c.args[0] == 'config/entity_registry/remove']
        assert 'sensor.andreas_iphone_12_pro_battery_level' in deleted_eids
        assert os.path.exists(audit)

    def test_singular_form_prompts_then_skips_on_no(self, patch_delete_env,
                                                    tmp_path):
        ws = patch_delete_env['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        # Singular form: should prompt y/N. Answering 'n' must skip the
        # delete but not crash. Using --yes to enter the commit path.
        result = runner.invoke(cli, [
            'delete', 'entity',
            'sensor.andreas_iphone_12_pro_battery_level',
            '--yes', '--audit', audit,
        ], input='n\n')
        # Live-state warning surfaces, user said no, no delete issued.
        assert 'live state' in result.output.lower() or \
               'REFUSED' in result.output
        for call in ws.call.call_args_list:
            assert call.args[0] != 'config/entity_registry/remove'

    def test_singular_form_prompts_then_proceeds_on_yes(
            self, patch_delete_env, tmp_path, monkeypatch):
        # Even saying 'y' to the live-state prompt won't actually delete
        # because the EXISTING recent-activity predicate is the next gate.
        # Force-disable that one so we can confirm the prompt-yes path
        # actually issues the call.
        monkeypatch.setattr(
            'hactl.handlers.deletions.safety_check_entity',
            lambda *a, **kw: (True, None))
        ws = patch_delete_env['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'entity',
            'sensor.andreas_iphone_12_pro_battery_level',
            '--yes', '--audit', audit,
        ], input='y\n')
        assert result.exit_code == 0, result.output
        ws.call.assert_called_with(
            'config/entity_registry/remove',
            entity_id='sensor.andreas_iphone_12_pro_battery_level')

    def test_dry_run_surfaces_warning_without_prompt(self, patch_delete_env,
                                                    tmp_path):
        # Dry-run path: warning printed, no prompt, no API call.
        ws = patch_delete_env['fake_ws']
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'entity',
            'sensor.andreas_iphone_12_pro_battery_level',
            '--dry-run',
        ])
        assert result.exit_code == 0
        assert 'live state' in result.output.lower() or \
               'REFUSED' in result.output
        ws.call.assert_not_called()


# ---------------------------------------------------------------------------
# TestStateOnlyUnavailableFilter
# ---------------------------------------------------------------------------

class TestStateOnlyUnavailableFilter:
    def test_state_only_unavailable_drops_live(self, patch_delete_env,
                                               tmp_path):
        ws = patch_delete_env['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'entities', '--filter', 'platform=mobile_app',
            '--state-only', 'unavailable',
            '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        # Live one was dropped before the safety predicate ever saw it.
        deleted_eids = [c.kwargs.get('entity_id')
                        for c in ws.call.call_args_list
                        if c.args[0] == 'config/entity_registry/remove']
        assert 'sensor.dead_iphone_battery_level' in deleted_eids
        assert 'sensor.andreas_iphone_12_pro_battery_level' \
               not in deleted_eids
        # And no REFUSED warning, because the live entity was filtered
        # out, not blocked.
        assert 'REFUSED' not in result.output

    def test_state_only_filter_pure_function(self, patch_delete_env):
        # Direct unit test of the helper.
        data = patch_delete_env['registries']
        ents = list(data['entities'])
        out = deletions.apply_state_only_filter(ents, data, 'unavailable')
        eids = {e['entity_id'] for e in out}
        assert 'sensor.dead_iphone_battery_level' in eids
        assert 'sensor.andreas_iphone_12_pro_battery_level' not in eids
