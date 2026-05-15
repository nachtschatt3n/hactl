"""
Tests for `hactl label` (list, apply, remove, --from-allowlist).

Covers:
  - TestLabelList            — registry list with usage counts
  - TestLabelApplyDevice     — single device by id and by name
  - TestLabelApplyEntity     — single entity by entity_id
  - TestLabelApplyFromAllowlist — YAML allowlist driver
  - TestLabelRemove          — strip a label
  - TestLabelDryRun          — default-on dry-run, no API calls, no audit
  - TestLabelAuditLog        — audit log structure
  - TestLabelIdempotent      — re-applying an existing label = no API call
  - TestLabelAllowlistFuzzyMatch — substring fallback warns but proceeds
  - TestLabelAllowlistNoMatch    — surfaces unmatched names
  - TestLabelAutoCreateMissing   — creates label_registry entry on demand
  - TestLabelMergesNotReplaces   — read-modify-write preserves existing labels
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest
import yaml
from click.testing import CliRunner

from hactl.cli import cli
from hactl.handlers import labels as labels_h


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registries():
    """Mixed device/entity/label registry with realistic shape."""
    return {
        'devices': [
            {
                'id': 'dev_soil',
                'name': 'Soil sensor 3',
                'name_by_user': None,
                'manufacturer': 'Aqara',
                'labels': [],
            },
            {
                'id': 'dev_shelly',
                'name': 'shelly_window',
                'name_by_user': 'Shelly Entry Window Blinds',
                'manufacturer': 'Shelly',
                'labels': ['existing_label'],
            },
            {
                'id': 'dev_other',
                'name': 'Living room lamp',
                'name_by_user': None,
                'manufacturer': 'Ikea',
                'labels': [],
            },
            {
                'id': 'dev_already',
                'name': 'Already Labeled',
                'name_by_user': None,
                'manufacturer': 'X',
                'labels': ['haghs_ignore'],
            },
        ],
        'entities': [
            {
                'entity_id': 'sensor.living_room_temp',
                'platform': 'mqtt',
                'device_id': 'dev_other',
                'labels': [],
            },
            {
                'entity_id': 'sensor.preexisting',
                'platform': 'mqtt',
                'device_id': None,
                'labels': ['keepme'],
            },
        ],
        'labels': [
            {'label_id': 'existing_label', 'name': 'existing_label',
             'description': '', 'color': ''},
            {'label_id': 'keepme', 'name': 'keepme',
             'description': '', 'color': ''},
        ],
        'ws_ok': True,
    }


@pytest.fixture
def fake_ws():
    ws = MagicMock()
    ws.connect.return_value = None
    ws.close.return_value = None
    ws.call.return_value = None
    return ws


@pytest.fixture
def patched(monkeypatch, registries, fake_ws):
    """Patch load_config + fetch_registries + WebSocketClient."""
    monkeypatch.setenv('HASS_URL', 'https://test-hass.example.com')
    monkeypatch.setenv('HASS_TOKEN', 'test_token_12345')
    monkeypatch.setattr(
        'hactl.handlers.labels.load_config',
        lambda: ('https://test-hass.example.com', 'test_token_12345'))
    monkeypatch.setattr(
        'hactl.handlers.labels.fetch_registries',
        lambda *_a, **_kw: registries)
    monkeypatch.setattr(
        'hactl.handlers.labels.WebSocketClient',
        lambda *a, **kw: fake_ws)
    return {'ws': fake_ws, 'registries': registries}


@pytest.fixture
def allowlist_path(tmp_path):
    """Write a cberg-style noise_allowlist.yaml fixture."""
    payload = {
        'flaky_zigbee_devices': [
            'Soil sensor 3',
        ],
        'flaky_iot_devices': [
            {'name': 'Shelly Entry Window Blinds',
             'note': 'WiFi flap'},
            {'name': 'Definitely Not A Real Device',
             'note': 'should not match anything'},
        ],
        # Other sections must be ignored.
        'recurring_alerts': [
            {'alertname': 'CPUThrottlingHigh', 'note': 'noise'},
        ],
    }
    p = tmp_path / 'noise_allowlist.yaml'
    p.write_text(yaml.safe_dump(payload))
    return str(p)


# ---------------------------------------------------------------------------
# TestLabelList
# ---------------------------------------------------------------------------

class TestLabelList:
    def test_list_table(self, patched):
        runner = CliRunner()
        result = runner.invoke(cli, ['label', 'list'])
        assert result.exit_code == 0, result.output
        # Both registry labels surface; usage counts come from the
        # registry fixtures above.
        assert 'existing_label' in result.output
        assert 'keepme' in result.output
        # haghs_ignore is in use on dev_already but not registered →
        # surfaces as (unregistered).
        assert 'haghs_ignore' in result.output

    def test_list_json(self, patched):
        runner = CliRunner()
        result = runner.invoke(cli, ['label', 'list', '-o', 'json'])
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        by_id = {r['label_id']: r for r in rows}
        assert 'existing_label' in by_id
        assert by_id['existing_label']['devices'] == 1
        assert by_id['keepme']['entities'] == 1
        # Unregistered-but-in-use label surfaces.
        assert by_id['haghs_ignore']['devices'] == 1


# ---------------------------------------------------------------------------
# TestLabelApplyDevice
# ---------------------------------------------------------------------------

class TestLabelApplyDevice:
    def test_apply_by_id_dry_run(self, patched):
        ws = patched['ws']
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_soil',
            '--label', 'haghs_ignore', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert 'dev_soil' in result.output or 'Soil sensor 3' in result.output
        assert 'haghs_ignore' in result.output
        ws.call.assert_not_called()

    def test_apply_by_id_yes(self, patched, tmp_path):
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_soil',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        # Should create the label first (it's not in the registry),
        # then update the device. Verify the update was made with a
        # MERGED labels list, not a replacement-of-empty.
        update_calls = [c for c in ws.call.call_args_list
                        if c.args[0] == 'config/device_registry/update']
        assert len(update_calls) == 1
        assert update_calls[0].kwargs['device_id'] == 'dev_soil'
        assert update_calls[0].kwargs['labels'] == ['haghs_ignore']
        assert os.path.exists(audit)

    def test_apply_by_name(self, patched, tmp_path):
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'soil sensor 3',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        update_calls = [c for c in ws.call.call_args_list
                        if c.args[0] == 'config/device_registry/update']
        assert update_calls[0].kwargs['device_id'] == 'dev_soil'

    def test_apply_unknown_device_reports(self, patched):
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'does-not-exist',
            '--label', 'haghs_ignore', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert 'Unmatched' in result.output
        assert 'does-not-exist' in result.output


# ---------------------------------------------------------------------------
# TestLabelApplyEntity
# ---------------------------------------------------------------------------

class TestLabelApplyEntity:
    def test_apply_entity_dry_run(self, patched):
        ws = patched['ws']
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--entity', 'sensor.living_room_temp',
            '--label', 'haghs_ignore', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert 'sensor.living_room_temp' in result.output
        ws.call.assert_not_called()

    def test_apply_entity_yes(self, patched, tmp_path):
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--entity', 'sensor.living_room_temp',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        ent_calls = [c for c in ws.call.call_args_list
                     if c.args[0] == 'config/entity_registry/update']
        assert len(ent_calls) == 1
        assert ent_calls[0].kwargs['entity_id'] == 'sensor.living_room_temp'
        assert ent_calls[0].kwargs['labels'] == ['haghs_ignore']


# ---------------------------------------------------------------------------
# TestLabelApplyFromAllowlist
# ---------------------------------------------------------------------------

class TestLabelApplyFromAllowlist:
    def test_dry_run_matches_zigbee_and_iot(
            self, patched, allowlist_path):
        ws = patched['ws']
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--from-allowlist', allowlist_path,
            '--label', 'haghs_ignore', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        # Both the zigbee soil and iot Shelly should be matched.
        assert 'Soil sensor 3' in result.output
        assert 'Shelly Entry Window Blinds' in result.output
        # The fake one should be reported as unmatched.
        assert 'Definitely Not A Real Device' in result.output
        assert 'Unmatched' in result.output
        ws.call.assert_not_called()

    def test_yes_applies_to_all_matched(
            self, patched, allowlist_path, tmp_path):
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--from-allowlist', allowlist_path,
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        device_ids_called = sorted(
            c.kwargs['device_id'] for c in ws.call.call_args_list
            if c.args[0] == 'config/device_registry/update')
        # dev_soil and dev_shelly both updated; dev_other ignored.
        assert device_ids_called == ['dev_shelly', 'dev_soil']


# ---------------------------------------------------------------------------
# TestLabelRemove
# ---------------------------------------------------------------------------

class TestLabelRemove:
    def test_remove_by_id_dry_run(self, patched):
        ws = patched['ws']
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'remove', '--device', 'dev_already',
            '--label', 'haghs_ignore', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        # Plan should show the label going away.
        assert 'haghs_ignore' in result.output
        ws.call.assert_not_called()

    def test_remove_by_id_yes(self, patched, tmp_path):
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'remove', '--device', 'dev_already',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        update_calls = [c for c in ws.call.call_args_list
                        if c.args[0] == 'config/device_registry/update']
        assert update_calls[0].kwargs['device_id'] == 'dev_already'
        assert update_calls[0].kwargs['labels'] == []


# ---------------------------------------------------------------------------
# TestLabelDryRun
# ---------------------------------------------------------------------------

class TestLabelDryRun:
    def test_default_is_dry_run_no_audit(self, patched, tmp_path):
        ws = patched['ws']
        audit = str(tmp_path / 'should-not-exist.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_soil',
            '--label', 'haghs_ignore', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        assert 'DRY-RUN' in result.output
        ws.call.assert_not_called()
        assert not os.path.exists(audit)

    def test_explicit_dry_run_no_audit(self, patched, tmp_path):
        audit = str(tmp_path / 'should-not-exist.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_soil',
            '--label', 'haghs_ignore', '--dry-run', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        assert not os.path.exists(audit)


# ---------------------------------------------------------------------------
# TestLabelAuditLog
# ---------------------------------------------------------------------------

class TestLabelAuditLog:
    def test_audit_log_structure(self, patched, tmp_path):
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_soil',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        with open(audit) as f:
            doc = json.load(f)
        assert doc['hactl_version']
        assert doc['invocation']
        assert doc['records']
        rec = doc['records'][0]
        assert rec['kind'] == 'device'
        assert rec['id'] == 'dev_soil'
        assert rec['op'] == 'add'
        assert rec['label'] == 'haghs_ignore'
        assert rec['pre_labels'] == []
        assert rec['post_labels'] == ['haghs_ignore']
        assert rec['result'] == 'updated'
        # And the label-create event was captured.
        assert any(c['label_id'] == 'haghs_ignore'
                   for c in doc['label_creations'])


# ---------------------------------------------------------------------------
# TestLabelIdempotent
# ---------------------------------------------------------------------------

class TestLabelIdempotent:
    def test_relabel_already_labeled_is_noop(self, patched, tmp_path):
        """CRITICAL: re-applying an existing label fires zero API calls.

        dev_already already has haghs_ignore. The label is also already
        present in the registry (because we install it in the registry
        for this test below) — so neither a label_create nor a
        device_registry/update should happen.
        """
        # Make sure the label is in the registry so no create-needed.
        patched['registries']['labels'].append(
            {'label_id': 'haghs_ignore', 'name': 'haghs_ignore'})
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_already',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        # Zero API calls — fully idempotent.
        assert ws.call.call_count == 0
        # And the run reports 'No changes required'.
        assert 'idempotent' in result.output.lower() \
               or 'no changes' in result.output.lower()


# ---------------------------------------------------------------------------
# TestLabelAllowlistFuzzyMatch
# ---------------------------------------------------------------------------

class TestLabelAllowlistFuzzyMatch:
    def test_substring_fallback_warns_and_matches(
            self, patched, tmp_path):
        """An allowlist entry with no exact match falls back to substring."""
        # The fixture has 'Living room lamp' as device name; we
        # allowlist a partial 'living room'.
        payload = {'flaky_iot_devices': [
            {'name': 'Living room', 'note': 'partial'},
        ]}
        p = tmp_path / 'partial.yaml'
        p.write_text(yaml.safe_dump(payload))
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--from-allowlist', str(p),
            '--label', 'haghs_ignore', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert 'Fuzzy' in result.output
        assert 'Living room' in result.output


# ---------------------------------------------------------------------------
# TestLabelAllowlistNoMatch
# ---------------------------------------------------------------------------

class TestLabelAllowlistNoMatch:
    def test_unmatched_entries_reported(self, patched, tmp_path):
        payload = {'flaky_zigbee_devices': [
            'Nope nope nope',
            'Also not real',
        ]}
        p = tmp_path / 'allno.yaml'
        p.write_text(yaml.safe_dump(payload))
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--from-allowlist', str(p),
            '--label', 'haghs_ignore', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert 'Unmatched' in result.output
        assert 'Nope nope nope' in result.output
        assert 'Also not real' in result.output


# ---------------------------------------------------------------------------
# TestLabelAutoCreateMissing
# ---------------------------------------------------------------------------

class TestLabelAutoCreateMissing:
    def test_target_label_auto_created_when_missing(
            self, patched, tmp_path):
        """CRITICAL: the target label is auto-created in label_registry."""
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_soil',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        create_calls = [c for c in ws.call.call_args_list
                        if c.args[0] == 'config/label_registry/create']
        assert len(create_calls) == 1
        # Should have used the same id as the name.
        assert create_calls[0].kwargs.get('name') == 'haghs_ignore' \
               or create_calls[0].kwargs.get('label_id') == 'haghs_ignore'

    def test_existing_label_not_recreated(self, patched, tmp_path):
        # Install haghs_ignore in the registry — apply must NOT create it.
        patched['registries']['labels'].append(
            {'label_id': 'haghs_ignore', 'name': 'haghs_ignore'})
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_soil',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        create_calls = [c for c in ws.call.call_args_list
                        if c.args[0] == 'config/label_registry/create']
        assert len(create_calls) == 0


# ---------------------------------------------------------------------------
# TestLabelMergesNotReplaces
# ---------------------------------------------------------------------------

class TestLabelMergesNotReplaces:
    def test_apply_preserves_existing_labels(self, patched, tmp_path):
        """dev_shelly already has ['existing_label']; applying haghs_ignore
        must end up with BOTH labels — HA's update API replaces, so this
        proves we're doing read-modify-write correctly."""
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'apply', '--device', 'dev_shelly',
            '--label', 'haghs_ignore', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        update = [c for c in ws.call.call_args_list
                  if c.args[0] == 'config/device_registry/update'][0]
        # Sorted set semantics — both labels survive.
        assert update.kwargs['labels'] == ['existing_label', 'haghs_ignore']

    def test_remove_preserves_other_labels(self, patched, tmp_path):
        """sensor.preexisting has ['keepme']; removing 'keepme' leaves []."""
        ws = patched['ws']
        audit = str(tmp_path / 'audit.json')
        runner = CliRunner()
        result = runner.invoke(cli, [
            'label', 'remove', '--entity', 'sensor.preexisting',
            '--label', 'keepme', '--yes', '--audit', audit,
        ])
        assert result.exit_code == 0, result.output
        update = [c for c in ws.call.call_args_list
                  if c.args[0] == 'config/entity_registry/update'][0]
        assert update.kwargs['labels'] == []


# ---------------------------------------------------------------------------
# Pure-function unit tests (no CLI runner, no patching).
# ---------------------------------------------------------------------------

class TestParseAllowlist:
    def test_extracts_string_and_object_forms(self, tmp_path):
        p = tmp_path / 'a.yaml'
        p.write_text(yaml.safe_dump({
            'flaky_zigbee_devices': ['One', 'Two'],
            'flaky_iot_devices': [
                {'name': 'Three', 'note': 'x'},
                {'name': 'Four'},
            ],
            'recurring_alerts': [{'alertname': 'X'}],  # ignored
        }))
        names = labels_h.parse_allowlist(str(p))
        assert names == ['One', 'Two', 'Three', 'Four']

    def test_dedup_case_insensitive(self, tmp_path):
        p = tmp_path / 'a.yaml'
        p.write_text(yaml.safe_dump({
            'flaky_zigbee_devices': ['Foo', 'foo', 'FOO'],
        }))
        names = labels_h.parse_allowlist(str(p))
        assert names == ['Foo']

    def test_invalid_yaml_raises(self, tmp_path):
        p = tmp_path / 'bad.yaml'
        p.write_text(': not yaml :\n  : at all :')
        with pytest.raises(Exception):
            labels_h.parse_allowlist(str(p))


class TestPlannedLabels:
    def test_add_dedups_and_sorts(self):
        cur, new = labels_h._planned_labels(
            ['b', 'a'], 'c', add=True)
        assert cur == ['a', 'b']
        assert new == ['a', 'b', 'c']

    def test_add_existing_is_noop(self):
        cur, new = labels_h._planned_labels(
            ['a', 'b'], 'a', add=True)
        assert cur == new == ['a', 'b']

    def test_remove_existing(self):
        _cur, new = labels_h._planned_labels(
            ['a', 'b'], 'a', add=False)
        assert new == ['b']

    def test_remove_missing_is_noop(self):
        cur, new = labels_h._planned_labels(
            ['a'], 'b', add=False)
        assert cur == new == ['a']
