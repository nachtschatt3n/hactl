"""
Tests for `hactl delete` (devices, entities, config-entries).

Covers:
  - singular: device, entity, config-entry
  - bulk by --filter: devices --filter category=orphan
  - bulk by manifest (-f file and -f -)
  - safety predicate refuse / --force bypass
  - dry-run default (no --yes => no API calls, no audit log)
  - audit log written on real delete
  - --limit cap and --force bypass
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from hactl.cli import cli
from hactl.handlers import deletions


# ---------------------------------------------------------------------------
# Fixtures: a richer registry shape than the get-tests one.
# ---------------------------------------------------------------------------

@pytest.fixture
def registries():
    """A small but expressive HA registry fixture."""
    return {
        'devices': [
            # 0: orphan device on a NOT_LOADED entry — safe to delete
            {
                'id': 'dev_orphan',
                'name': 'Orphan Device',
                'name_by_user': None,
                'manufacturer': 'OldVendor',
                'model': 'X1',
                'area_id': None,
                'config_entries': ['ce_dead'],
                'disabled_by': None,
            },
            # 1: live device on a LOADED entry with active entity
            {
                'id': 'dev_live',
                'name': 'Live Device',
                'name_by_user': None,
                'manufacturer': 'NewVendor',
                'model': 'Y2',
                'area_id': 'kitchen',
                'config_entries': ['ce_live'],
                'disabled_by': None,
            },
            # 2: disabled device (intentional)
            {
                'id': 'dev_disabled',
                'name': 'Disabled Device',
                'name_by_user': None,
                'manufacturer': 'X',
                'model': 'Z',
                'area_id': None,
                'config_entries': ['ce_dead'],
                'disabled_by': 'user',
            },
        ],
        'entities': [
            {
                'entity_id': 'sensor.orphan_temp',
                'platform': 'oldintegration',
                'config_entry_id': 'ce_dead',
                'device_id': 'dev_orphan',
                'disabled_by': None,
            },
            {
                'entity_id': 'sensor.live_temp',
                'platform': 'newintegration',
                'config_entry_id': 'ce_live',
                'device_id': 'dev_live',
                'disabled_by': None,
            },
            {
                'entity_id': 'sensor.tibber_price_now',
                'platform': 'tibber_prices',
                'config_entry_id': 'ce_dead',
                'device_id': None,
                'disabled_by': None,
            },
        ],
        'areas': [{'area_id': 'kitchen', 'name': 'Kitchen'}],
        'config_entries': [
            {'entry_id': 'ce_dead', 'domain': 'oldintegration',
             'state': 'not_loaded', 'source': 'user', 'title': 'Old'},
            {'entry_id': 'ce_live', 'domain': 'newintegration',
             'state': 'loaded', 'source': 'user', 'title': 'New'},
        ],
        'states': [
            {'entity_id': 'sensor.orphan_temp', 'state': 'unavailable',
             'attributes': {}},
            {'entity_id': 'sensor.live_temp', 'state': '21.5',
             'attributes': {}},
            {'entity_id': 'sensor.restored_only', 'state': '5',
             'attributes': {'restored': True}},
        ],
        'ws_ok': True,
    }


@pytest.fixture
def fake_ws():
    """Mock WebSocketClient — captures every call() invocation."""
    ws = MagicMock()
    ws.connect.return_value = None
    ws.close.return_value = None
    ws.call.return_value = None
    return ws


@pytest.fixture
def patch_env_and_registries(monkeypatch, registries, fake_ws, tmp_path):
    """Patch load_config, fetch_registries, WebSocketClient, and history."""
    monkeypatch.setenv('HASS_URL', 'https://test-hass.example.com')
    monkeypatch.setenv('HASS_TOKEN', 'test_token_12345')

    monkeypatch.setattr(
        'hactl.handlers.deletions.load_config',
        lambda: ('https://test-hass.example.com', 'test_token_12345'))
    monkeypatch.setattr(
        'hactl.commands.delete.deletions.load_config',
        lambda: ('https://test-hass.example.com', 'test_token_12345'),
        raising=False)
    # The delete commands import load_config from hactl.core directly.
    monkeypatch.setattr(
        'hactl.core.config.load_config',
        lambda: ('https://test-hass.example.com', 'test_token_12345'))

    monkeypatch.setattr(
        'hactl.handlers.deletions.fetch_registries',
        lambda *_a, **_kw: registries)

    # WebSocketClient(...) returns the fake_ws.
    monkeypatch.setattr(
        'hactl.handlers.deletions.WebSocketClient',
        lambda *a, **kw: fake_ws)

    # Default: no recent activity for any entity (so safety predicate
    # only blocks on `loaded + recent activity`, not on transient errors).
    monkeypatch.setattr(
        'hactl.handlers.deletions._has_recent_activity_for_entity',
        lambda *a, **kw: False)

    # Audit logs go into the test tmpdir.
    audit_dir = tmp_path / 'audit'
    audit_dir.mkdir()
    return {'fake_ws': fake_ws, 'audit_dir': str(audit_dir),
            'registries': registries}


# ---------------------------------------------------------------------------
# TestDeleteDevice — singular form
# ---------------------------------------------------------------------------

class TestDeleteDevice:
    def test_delete_device_dry_run_makes_no_api_call(
            self, patch_env_and_registries):
        ws = patch_env_and_registries['fake_ws']
        runner = CliRunner()
        result = runner.invoke(
            cli, ['delete', 'device', 'dev_orphan', '--dry-run'])
        assert result.exit_code == 0, result.output
        assert 'Delete plan' in result.output
        assert 'dev_orphan' in result.output
        ws.call.assert_not_called()

    def test_delete_device_default_is_dry_run(self, patch_env_and_registries):
        ws = patch_env_and_registries['fake_ws']
        runner = CliRunner()
        result = runner.invoke(cli, ['delete', 'device', 'dev_orphan'])
        assert result.exit_code == 0, result.output
        assert 'DRY-RUN' in result.output
        ws.call.assert_not_called()

    def test_delete_device_yes_calls_remove_config_entry(
            self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'dev_orphan',
            '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        # Should have called remove_config_entry with device_id+config_entry_id
        ws.call.assert_called_with(
            'config/device_registry/remove_config_entry',
            device_id='dev_orphan',
            config_entry_id='ce_dead',
        )
        assert os.path.exists(audit)

    def test_delete_device_by_name(self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'Orphan Device',
            '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        assert ws.call.called

    def test_delete_unknown_device_skips(self, patch_env_and_registries):
        runner = CliRunner()
        result = runner.invoke(
            cli, ['delete', 'device', 'does-not-exist', '--dry-run'])
        # Not found => no targets => exit 0 with notice.
        assert result.exit_code == 0
        assert 'not found' in result.output or 'Nothing to delete' in result.output


# ---------------------------------------------------------------------------
# TestDeleteEntity
# ---------------------------------------------------------------------------

class TestDeleteEntity:
    def test_delete_entity_dry_run(self, patch_env_and_registries):
        ws = patch_env_and_registries['fake_ws']
        runner = CliRunner()
        result = runner.invoke(
            cli, ['delete', 'entity', 'sensor.orphan_temp', '--dry-run'])
        assert result.exit_code == 0, result.output
        ws.call.assert_not_called()

    def test_delete_entity_yes_calls_registry_remove(
            self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'entity', 'sensor.orphan_temp',
            '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        ws.call.assert_called_with(
            'config/entity_registry/remove',
            entity_id='sensor.orphan_temp',
        )

    def test_delete_restored_only_entity_errors(
            self, patch_env_and_registries, tmp_path):
        # Entity exists only in /api/states (restored=True) — not registry.
        # Should fail at execute time with a clear error.
        ws = patch_env_and_registries['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'entity', 'sensor.restored_only',
            '--yes', '--audit', audit, '--force',
        ])
        # Exits non-zero because the single record fails.
        assert result.exit_code != 0
        # And no entity_registry/remove was issued.
        for call in ws.call.call_args_list:
            assert call.args[0] != 'config/entity_registry/remove'


# ---------------------------------------------------------------------------
# TestDeleteConfigEntry
# ---------------------------------------------------------------------------

class TestDeleteConfigEntry:
    def test_delete_config_entry_dry_run(self, patch_env_and_registries):
        ws = patch_env_and_registries['fake_ws']
        runner = CliRunner()
        result = runner.invoke(
            cli, ['delete', 'config-entry', 'ce_dead', '--dry-run'])
        assert result.exit_code == 0, result.output
        assert 'ce_dead' in result.output
        ws.call.assert_not_called()

    def test_delete_config_entry_yes_calls_delete(
            self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'config-entry', 'ce_dead',
            '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        ws.call.assert_called_with('config_entries/delete',
                                   entry_id='ce_dead')


# ---------------------------------------------------------------------------
# TestDeleteFromFile
# ---------------------------------------------------------------------------

class TestDeleteFromFile:
    def test_delete_from_file_mixed_kinds(
            self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        manifest = tmp_path / 'plan.json'
        manifest.write_text(json.dumps([
            {'kind': 'device', 'id': 'dev_orphan'},
            {'kind': 'entity', 'id': 'sensor.orphan_temp'},
            {'kind': 'config-entry', 'id': 'ce_dead'},
        ]))
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', '-f', str(manifest),
            '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        # All three call types should have been issued.
        kinds_called = {c.args[0] for c in ws.call.call_args_list}
        assert 'config/device_registry/remove_config_entry' in kinds_called
        assert 'config/entity_registry/remove' in kinds_called
        assert 'config_entries/delete' in kinds_called

    def test_delete_from_stdin(
            self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        payload = json.dumps([{'kind': 'entity',
                               'id': 'sensor.orphan_temp'}])
        result = runner.invoke(cli, [
            'delete', '-f', '-', '--yes', '--audit', audit,
        ], input=payload)
        assert result.exit_code == 0, result.output
        ws.call.assert_called_with(
            'config/entity_registry/remove',
            entity_id='sensor.orphan_temp')

    def test_delete_from_file_zombie_shape(
            self, patch_env_and_registries, tmp_path):
        # `hactl get zombie-devices -o json` shape uses entity_id/device_id.
        manifest = tmp_path / 'zombies.json'
        manifest.write_text(json.dumps([
            {'category': 'orphan', 'device_id': 'dev_orphan',
             'entity_id': None},
            {'category': 'restored_entity', 'device_id': None,
             'entity_id': 'sensor.orphan_temp'},
        ]))
        runner = CliRunner()
        result = runner.invoke(cli, ['delete', '-f', str(manifest),
                                     '--dry-run'])
        assert result.exit_code == 0, result.output
        assert 'dev_orphan' in result.output
        assert 'sensor.orphan_temp' in result.output


# ---------------------------------------------------------------------------
# TestDeleteFilter
# ---------------------------------------------------------------------------

class TestDeleteFilter:
    def test_delete_devices_filter_category_stalled(
            self, patch_env_and_registries):
        # dev_orphan has one enabled entity (sensor.orphan_temp) whose
        # state is 'unavailable' → classified as 'stalled', not 'orphan'.
        # dev_live has a live entity → not stalled.
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'devices', '--filter', 'category=stalled',
            '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert 'dev_orphan' in result.output
        assert 'dev_live' not in result.output

    def test_delete_entities_filter_platform(
            self, patch_env_and_registries):
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'entities', '--filter', 'platform=tibber_prices',
            '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert 'tibber_price_now' in result.output

    def test_delete_config_entries_filter_state(
            self, patch_env_and_registries):
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'config-entries', '--filter', 'state=not_loaded',
            '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert 'ce_dead' in result.output
        assert 'ce_live' not in result.output


# ---------------------------------------------------------------------------
# TestDeleteSafetyPredicate
# ---------------------------------------------------------------------------

class TestDeleteSafetyPredicate:
    def test_safety_blocks_loaded_with_recent_activity(
            self, patch_env_and_registries, monkeypatch, tmp_path):
        """LIFELINE: refuses to delete loaded-integration device w/ activity."""
        ws = patch_env_and_registries['fake_ws']
        # Force "recent activity = True" globally.
        monkeypatch.setattr(
            'hactl.handlers.deletions._has_recent_activity_for_entity',
            lambda *a, **kw: True)
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'dev_live', '--yes', '--audit', audit,
        ])
        # Safety should drop dev_live; nothing left to delete.
        assert 'blocked' in result.output.lower() or 'safety' in result.output.lower()
        ws.call.assert_not_called()

    def test_force_bypasses_safety_predicate(
            self, patch_env_and_registries, monkeypatch, tmp_path):
        """LIFELINE: --force lets a dangerous delete through (still audited)."""
        ws = patch_env_and_registries['fake_ws']
        monkeypatch.setattr(
            'hactl.handlers.deletions._has_recent_activity_for_entity',
            lambda *a, **kw: True)
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'dev_live',
            '--yes', '--force', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        ws.call.assert_called_with(
            'config/device_registry/remove_config_entry',
            device_id='dev_live', config_entry_id='ce_live')
        # Audit log MUST still exist with --force.
        assert os.path.exists(audit)

    def test_disabled_device_blocked_without_force(
            self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'dev_disabled',
            '--yes', '--audit', audit,
        ])
        assert 'disabled_by' in result.output or 'safety' in result.output.lower()
        ws.call.assert_not_called()


# ---------------------------------------------------------------------------
# TestDeleteDryRun
# ---------------------------------------------------------------------------

class TestDeleteDryRun:
    def test_dry_run_writes_no_audit(self, patch_env_and_registries, tmp_path):
        audit = str(tmp_path / 'should-not-exist.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'dev_orphan',
            '--dry-run', '--audit', audit,
        ])
        assert result.exit_code == 0
        assert not os.path.exists(audit)

    def test_no_yes_means_dry_run_default(
            self, patch_env_and_registries, tmp_path):
        audit = str(tmp_path / 'should-not-exist.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'dev_orphan', '--audit', audit,
        ])
        assert result.exit_code == 0
        assert not os.path.exists(audit)
        assert 'DRY-RUN' in result.output


# ---------------------------------------------------------------------------
# TestDeleteAuditLog
# ---------------------------------------------------------------------------

class TestDeleteAuditLog:
    def test_audit_log_written_on_real_delete(
            self, patch_env_and_registries, tmp_path):
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'dev_orphan',
            '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        assert os.path.exists(audit)
        with open(audit) as f:
            doc = json.load(f)
        assert doc['hactl_version']
        assert doc['invocation']
        assert len(doc['records']) == 1
        assert doc['records'][0]['kind'] == 'device'
        assert doc['records'][0]['result'] == 'deleted'
        assert doc['records'][0]['pre_state']['id'] == 'dev_orphan'

    def test_audit_log_captures_failures(
            self, patch_env_and_registries, tmp_path, monkeypatch):
        ws = patch_env_and_registries['fake_ws']
        ws.call.side_effect = RuntimeError('simulated WS failure')
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', 'device', 'dev_orphan',
            '--yes', '--audit', audit,
        ])
        assert result.exit_code != 0
        with open(audit) as f:
            doc = json.load(f)
        assert doc['records'][0]['result'] == 'failed'
        assert 'simulated' in doc['records'][0]['error']


# ---------------------------------------------------------------------------
# TestDeleteLimit
# ---------------------------------------------------------------------------

class TestDeleteLimit:
    def test_limit_blocks_oversized_batch(
            self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        manifest = tmp_path / 'big.json'
        # 3 records, --limit 2 → blocked.
        manifest.write_text(json.dumps([
            {'kind': 'device', 'id': 'dev_orphan'},
            {'kind': 'entity', 'id': 'sensor.orphan_temp'},
            {'kind': 'config-entry', 'id': 'ce_dead'},
        ]))
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', '-f', str(manifest),
            '--limit', '2', '--yes', '--audit', audit,
        ])
        assert result.exit_code != 0
        assert 'limit' in result.output.lower()
        ws.call.assert_not_called()

    def test_force_bypasses_limit(
            self, patch_env_and_registries, tmp_path):
        ws = patch_env_and_registries['fake_ws']
        manifest = tmp_path / 'big.json'
        manifest.write_text(json.dumps([
            {'kind': 'device', 'id': 'dev_orphan'},
            {'kind': 'entity', 'id': 'sensor.orphan_temp'},
            {'kind': 'config-entry', 'id': 'ce_dead'},
        ]))
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'delete', '-f', str(manifest),
            '--limit', '2', '--force', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        assert ws.call.called


# ---------------------------------------------------------------------------
# Pure-function unit tests (no CLI runner).
# ---------------------------------------------------------------------------

class TestDeletionsHelpers:
    def test_parse_filters_basic(self):
        out = deletions.parse_filters(('a=1', 'b=2'))
        assert out == {'a': '1', 'b': '2'}

    def test_parse_filters_invalid(self):
        with pytest.raises(Exception):
            deletions.parse_filters(('badformat',))

    def test_resolve_device_by_id(self, registries):
        d = deletions.resolve_device(registries, 'dev_orphan')
        assert d is not None
        assert d['id'] == 'dev_orphan'

    def test_resolve_device_by_name(self, registries):
        d = deletions.resolve_device(registries, 'orphan device')
        assert d is not None
        assert d['id'] == 'dev_orphan'

    def test_resolve_device_missing(self, registries):
        assert deletions.resolve_device(registries, 'nope') is None

    def test_filter_devices_integration(self, registries):
        out = deletions.filter_devices(
            registries, {'integration': 'newintegration'})
        assert [d['id'] for d in out] == ['dev_live']

    def test_filter_entities_restored(self, registries):
        # No entry for sensor.restored_only in entity registry, so
        # restored-true filter returns empty here (it's intentional —
        # restored entities lacking a registry record can't be deleted
        # via entity_registry/remove).
        out = deletions.filter_entities(registries, {'restored': 'true'})
        assert out == []
