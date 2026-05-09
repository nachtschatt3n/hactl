"""
Tests for dashboard drift detection / backup behaviour.

Covers:
  * `_normalize_for_diff` and `_configs_equivalent` ignore HA-injected trivia
    (top-level `version`, sprinkled `None`s) but flag structural differences.
  * `update_dashboard` writes a backup before saving and stamps the new config
    on the WebSocket call.
  * `update_dashboard` aborts (no save) when the live config has drifted from
    the on-disk source, unless `--force` is given.
  * `pull_dashboard` writes the live config to the requested path.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import click
import pytest

from hactl.handlers import dashboard_ops


# ---- pure helpers ---------------------------------------------------------

class TestConfigsEquivalent:
    def test_identical_configs_are_equivalent(self):
        cfg = {"title": "x", "views": [{"title": "v1", "cards": []}]}
        assert dashboard_ops._configs_equivalent(cfg, cfg)

    def test_top_level_version_is_ignored(self):
        live = {"version": 17, "title": "x", "views": []}
        disk = {"title": "x", "views": []}
        assert dashboard_ops._configs_equivalent(live, disk)

    def test_none_values_are_ignored(self):
        live = {"title": "x", "icon": None, "views": []}
        disk = {"title": "x", "views": []}
        assert dashboard_ops._configs_equivalent(live, disk)

    def test_structural_difference_is_detected(self):
        live = {"title": "x", "views": [{"title": "Real edits"}]}
        disk = {"title": "x", "views": [{"title": "Other"}]}
        assert not dashboard_ops._configs_equivalent(live, disk)

    def test_added_card_is_detected(self):
        live = {"views": [{"cards": [{"type": "entities"}, {"type": "markdown"}]}]}
        disk = {"views": [{"cards": [{"type": "entities"}]}]}
        assert not dashboard_ops._configs_equivalent(live, disk)

    def test_list_order_matters(self):
        # lovelace card order is semantically meaningful, so reordering counts as drift
        live = {"views": [{"cards": [{"type": "a"}, {"type": "b"}]}]}
        disk = {"views": [{"cards": [{"type": "b"}, {"type": "a"}]}]}
        assert not dashboard_ops._configs_equivalent(live, disk)


# ---- file-system helpers --------------------------------------------------

class TestBackupDir:
    def test_creates_backup_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        d = dashboard_ops._backup_dir()
        assert d.exists()
        assert d == tmp_path / ".hactl" / "backups"

    def test_unique_backup_path_increments_on_collision(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        # pre-create the first candidate
        first = dashboard_ops._unique_backup_path("foo", "20260509T120000Z")
        first.write_text("placeholder")
        second = dashboard_ops._unique_backup_path("foo", "20260509T120000Z")
        assert second.name.endswith("-2.yaml")
        assert second != first


# ---- update_dashboard end-to-end (with mocked websocket) ------------------

@pytest.fixture
def fake_ws(monkeypatch):
    """Patch WebSocketClient with a recorder so we can assert which calls
    happened in which order without ever touching the network."""
    instance = MagicMock()
    instance.connect.return_value = None
    instance.close.return_value = None

    # default: live config matches disk so update goes through cleanly
    instance._live_config = {"title": "Battery", "views": [{"title": "Main"}]}
    instance.calls = []

    def fake_call(message_type, **kwargs):
        instance.calls.append((message_type, kwargs))
        if message_type == "lovelace/config":
            if instance._live_config is None:
                raise click.ClickException("config_not_found")
            return instance._live_config
        if message_type == "lovelace/config/save":
            return None
        return None

    instance.call.side_effect = fake_call

    def factory(url, token):
        return instance

    monkeypatch.setattr("hactl.handlers.dashboard_ops.WebSocketClient", factory)
    monkeypatch.setattr(
        "hactl.handlers.dashboard_ops.load_config",
        lambda: ("https://test.example", "test-token"),
    )
    return instance


def _write_yaml(path: Path, payload: dict):
    import yaml
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


class TestUpdateDashboard:
    def test_clean_update_writes_backup_and_saves(self, tmp_path, monkeypatch, fake_ws, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        # disk == live (modulo HA-injected version) so no drift
        disk_payload = {"title": "Battery", "views": [{"title": "Main"}]}
        fake_ws._live_config = {"version": 7, **disk_payload}

        src = tmp_path / "battery.yaml"
        _write_yaml(src, disk_payload)

        dashboard_ops.update_dashboard("battery-monitor", str(src))

        out = capsys.readouterr().out
        assert "backup:" in out
        assert "Successfully updated dashboard" in out

        # backup file exists
        backups = list((tmp_path / ".hactl" / "backups").glob("dashboard_battery-monitor_*.yaml"))
        assert len(backups) == 1

        # save call happened *after* the fetch
        call_types = [c[0] for c in fake_ws.calls]
        assert call_types[0] == "lovelace/config"
        assert "lovelace/config/save" in call_types

    def test_drift_blocks_save_and_keeps_backup(self, tmp_path, monkeypatch, fake_ws, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        # live diverges from disk
        fake_ws._live_config = {"title": "Battery", "views": [{"title": "Main", "cards": [{"type": "entities"}]}]}

        src = tmp_path / "battery.yaml"
        _write_yaml(src, {"title": "Battery", "views": [{"title": "Main"}]})

        with pytest.raises(click.ClickException) as exc:
            dashboard_ops.update_dashboard("battery-monitor", str(src))

        msg = exc.value.message
        assert "has diverged from" in msg
        assert "to overwrite anyway: re-run with --force" in msg
        assert "hactl pull dashboard battery-monitor" in msg

        # save must NOT have happened
        call_types = [c[0] for c in fake_ws.calls]
        assert "lovelace/config/save" not in call_types

        # backup must still have been written
        backups = list((tmp_path / ".hactl" / "backups").glob("dashboard_battery-monitor_*.yaml"))
        assert len(backups) == 1

    def test_force_bypasses_drift_check(self, tmp_path, monkeypatch, fake_ws, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = {"title": "Battery", "views": [{"title": "Main", "cards": [{"type": "entities"}]}]}

        src = tmp_path / "battery.yaml"
        _write_yaml(src, {"title": "Battery", "views": [{"title": "Main"}]})

        dashboard_ops.update_dashboard("battery-monitor", str(src), force=True)

        call_types = [c[0] for c in fake_ws.calls]
        assert "lovelace/config/save" in call_types
        # backup still taken even on force
        backups = list((tmp_path / ".hactl" / "backups").glob("dashboard_battery-monitor_*.yaml"))
        assert len(backups) == 1


class TestPullDashboard:
    def test_pull_writes_live_config_to_disk(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = {"title": "Battery", "views": [{"title": "Main"}]}

        target = tmp_path / "out" / "battery.yaml"
        dashboard_ops.pull_dashboard("battery-monitor", str(target))

        assert target.exists()
        content = target.read_text()
        assert "Battery" in content
        assert "Main" in content

    def test_pull_missing_dashboard_raises(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None  # triggers config_not_found in fake call

        with pytest.raises(click.ClickException):
            dashboard_ops.pull_dashboard("does-not-exist", str(tmp_path / "x.yaml"))
