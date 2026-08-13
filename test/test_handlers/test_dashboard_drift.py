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
    # panel registry, as returned by lovelace/dashboards/list
    instance._dashboards = []
    # set to an exception to make lovelace/config/save blow up
    instance._save_error = None
    instance.calls = []

    def _is_registered(url_path):
        """Mirror Home Assistant: a config can only be saved against a panel
        that exists. A dashboard that already has a live config is by
        definition registered."""
        if any(d.get("url_path") == url_path for d in instance._dashboards):
            return True
        return instance._live_config is not None

    def fake_call(message_type, **kwargs):
        instance.calls.append((message_type, kwargs))
        if message_type == "lovelace/config":
            if instance._live_config is None:
                raise click.ClickException("config_not_found")
            return instance._live_config
        if message_type == "lovelace/config/save":
            if instance._save_error is not None:
                raise instance._save_error
            # This is the behaviour the create bug tripped over: HA refuses to
            # save a config for a url_path that has no registered panel.
            if not _is_registered(kwargs.get("url_path")):
                raise click.ClickException(
                    "WebSocket call failed: {'error': {'code': 'config_not_found', "
                    "'message': 'Unknown config specified: %s'}}" % kwargs.get("url_path")
                )
            instance._live_config = kwargs.get("config")
            return None
        if message_type == "lovelace/dashboards/list":
            return [dict(d) for d in instance._dashboards]
        if message_type == "lovelace/dashboards/create":
            entry = {"id": kwargs["url_path"].replace("-", "_"), **kwargs}
            instance._dashboards.append(entry)
            return dict(entry)
        if message_type == "lovelace/dashboards/delete":
            instance._dashboards = [
                d for d in instance._dashboards
                if d.get("id") != kwargs.get("dashboard_id")
            ]
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


class TestUnifiedDiff:
    def test_shows_changes(self):
        live = {"title": "New", "views": []}
        disk = {"title": "Old", "views": []}
        result = dashboard_ops._unified_diff(live, disk, "disk.yaml")
        assert "-title: Old" in result
        assert "+title: New" in result

    def test_truncates_long_diff(self):
        live = {str(i): "live" for i in range(50)}
        disk = {str(i): "disk" for i in range(50)}
        result = dashboard_ops._unified_diff(live, disk, "disk.yaml", max_lines=5)
        assert "truncated" in result


class TestCreateDashboard:
    def test_create_new_dashboard_saves_without_backup(self, tmp_path, monkeypatch, fake_ws, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None  # dashboard doesn't exist yet

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "New", "views": []})

        dashboard_ops.create_dashboard("new-dash", str(src))

        out = capsys.readouterr().out
        assert "Successfully created dashboard" in out
        assert "backup:" not in out

        call_types = [c[0] for c in fake_ws.calls]
        assert "lovelace/config/save" in call_types

    def test_create_existing_no_drift_takes_backup(self, tmp_path, monkeypatch, fake_ws, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        payload = {"title": "Battery", "views": [{"title": "Main"}]}
        fake_ws._live_config = {"version": 3, **payload}

        src = tmp_path / "battery.yaml"
        _write_yaml(src, payload)

        dashboard_ops.create_dashboard("battery-monitor", str(src))

        out = capsys.readouterr().out
        assert "backup:" in out
        assert "Successfully created dashboard" in out
        backups = list((tmp_path / ".hactl" / "backups").glob("dashboard_battery-monitor_*.yaml"))
        assert len(backups) == 1

    def test_create_existing_drift_blocks_and_includes_pull_hint(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = {"title": "Battery", "views": [{"title": "Edited"}]}

        src = tmp_path / "battery.yaml"
        _write_yaml(src, {"title": "Battery", "views": [{"title": "Original"}]})

        with pytest.raises(click.ClickException) as exc:
            dashboard_ops.create_dashboard("battery-monitor", str(src))

        msg = exc.value.message
        assert "already exists and has diverged from" in msg
        assert "to overwrite anyway: re-run with --force" in msg
        assert "hactl pull dashboard battery-monitor" in msg

        call_types = [c[0] for c in fake_ws.calls]
        assert "lovelace/config/save" not in call_types

    def test_create_force_bypasses_drift(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = {"title": "Battery", "views": [{"title": "Edited"}]}

        src = tmp_path / "battery.yaml"
        _write_yaml(src, {"title": "Battery", "views": [{"title": "Original"}]})

        dashboard_ops.create_dashboard("battery-monitor", str(src), force=True)

        call_types = [c[0] for c in fake_ws.calls]
        assert "lovelace/config/save" in call_types
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


# ---- panel registration on create ----------------------------------------

def _call_types(fake_ws):
    return [c[0] for c in fake_ws.calls]


def _call_kwargs(fake_ws, message_type):
    for mtype, kwargs in fake_ws.calls:
        if mtype == message_type:
            return kwargs
    return None


class TestFakeWsFidelity:
    """Guard the mock itself: saving a config against an unregistered panel
    must fail, otherwise the registration tests below prove nothing."""

    def test_save_without_registration_is_rejected(self, fake_ws):
        fake_ws._live_config = None
        fake_ws._dashboards = []
        with pytest.raises(click.ClickException) as exc:
            fake_ws.call("lovelace/config/save", url_path="ghost-dash", config={})
        assert "config_not_found" in str(exc.value)


class TestCreateDashboardRegistration:
    """`--create` must register the panel *and* save the config.

    Regression: create previously only called lovelace/config/save, which fails
    with config_not_found because no panel exists at that url_path yet.
    """

    def test_create_registers_panel_before_saving_config(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "New Dash", "views": []})

        dashboard_ops.create_dashboard("new-dash", str(src))

        types = _call_types(fake_ws)
        assert "lovelace/dashboards/create" in types, "panel was never registered"
        assert "lovelace/config/save" in types
        # registration must come first, or the save fails
        assert types.index("lovelace/dashboards/create") < types.index("lovelace/config/save")

        # and the panel really is in the registry afterwards
        assert [d["url_path"] for d in fake_ws._dashboards] == ["new-dash"]

    def test_create_registration_payload(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "New Dash", "views": []})

        dashboard_ops.create_dashboard("new-dash", str(src))

        kwargs = _call_kwargs(fake_ws, "lovelace/dashboards/create")
        assert kwargs["url_path"] == "new-dash"
        assert kwargs["mode"] == "storage"
        assert kwargs["show_in_sidebar"] is True
        assert kwargs["require_admin"] is False

    def test_title_defaults_to_config_title(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "Grill", "views": []})

        dashboard_ops.create_dashboard("dashboard-grill", str(src))

        assert _call_kwargs(fake_ws, "lovelace/dashboards/create")["title"] == "Grill"

    def test_title_falls_back_to_prettified_url_path(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"views": []})  # no title in the config

        dashboard_ops.create_dashboard("my-new-dash", str(src))

        assert _call_kwargs(fake_ws, "lovelace/dashboards/create")["title"] == "My New Dash"

    def test_explicit_title_icon_and_flags_are_used(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "Ignored", "views": []})

        dashboard_ops.create_dashboard(
            "dashboard-grill", str(src), title="BBQ", icon="mdi:grill",
            show_in_sidebar=False, require_admin=True,
        )

        kwargs = _call_kwargs(fake_ws, "lovelace/dashboards/create")
        assert kwargs["title"] == "BBQ"
        assert kwargs["icon"] == "mdi:grill"
        assert kwargs["show_in_sidebar"] is False
        assert kwargs["require_admin"] is True

    def test_icon_is_omitted_when_not_supplied(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "New", "views": []})

        dashboard_ops.create_dashboard("new-dash", str(src))

        # HA's schema rejects a null icon, so the key must be absent entirely
        assert "icon" not in _call_kwargs(fake_ws, "lovelace/dashboards/create")

    def test_rejects_new_url_path_without_hyphen(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "New", "views": []})

        with pytest.raises(click.ClickException) as exc:
            dashboard_ops.create_dashboard("nohyphen", str(src))

        assert "hyphen" in str(exc.value)
        # nothing was mutated
        assert "lovelace/dashboards/create" not in _call_types(fake_ws)
        assert "lovelace/config/save" not in _call_types(fake_ws)


class TestCreateDashboardIdempotency:
    """Re-running --create against an existing dashboard updates it and must
    never re-register or overwrite its sidebar registration."""

    def test_existing_panel_is_not_reregistered(self, tmp_path, monkeypatch, fake_ws, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        payload = {"title": "Grill", "views": [{"title": "Cook"}]}
        fake_ws._live_config = {"version": 2, **payload}
        fake_ws._dashboards = [{
            "id": "dashboard_grill", "url_path": "dashboard-grill",
            "title": "Grill", "icon": "mdi:grill",
            "show_in_sidebar": True, "require_admin": False, "mode": "storage",
        }]

        src = tmp_path / "grill.yaml"
        _write_yaml(src, payload)

        dashboard_ops.create_dashboard("dashboard-grill", str(src))

        types = _call_types(fake_ws)
        assert "lovelace/dashboards/create" not in types
        assert "lovelace/config/save" in types
        assert "panel already registered" in capsys.readouterr().out

    def test_existing_registration_is_not_clobbered(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        payload = {"title": "Grill", "views": [{"title": "Cook"}]}
        fake_ws._live_config = dict(payload)
        original = {
            "id": "dashboard_grill", "url_path": "dashboard-grill",
            "title": "Original Title", "icon": "mdi:original",
            "show_in_sidebar": True, "require_admin": False, "mode": "storage",
        }
        fake_ws._dashboards = [dict(original)]

        src = tmp_path / "grill.yaml"
        _write_yaml(src, payload)

        # even with conflicting registration options, the existing panel wins
        dashboard_ops.create_dashboard(
            "dashboard-grill", str(src), title="Hijacked",
            icon="mdi:hijack", show_in_sidebar=False, require_admin=True,
        )

        assert fake_ws._dashboards == [original]
        assert "lovelace/dashboards/update" not in _call_types(fake_ws)

    def test_hyphenless_path_allowed_when_already_registered(self, tmp_path, monkeypatch, fake_ws):
        """The hyphen rule only constrains *new* panels; `map` already exists."""
        monkeypatch.setenv("HOME", str(tmp_path))
        payload = {"title": "Map", "views": []}
        fake_ws._live_config = dict(payload)
        fake_ws._dashboards = [{"id": "map", "url_path": "map", "title": "Map"}]

        src = tmp_path / "map.yaml"
        _write_yaml(src, payload)

        dashboard_ops.create_dashboard("map", str(src))

        assert "lovelace/config/save" in _call_types(fake_ws)

    def test_drift_on_existing_dashboard_still_blocks_create(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = {"title": "Grill", "views": [{"title": "Edited in UI"}]}
        fake_ws._dashboards = [{"id": "dashboard_grill", "url_path": "dashboard-grill"}]

        src = tmp_path / "grill.yaml"
        _write_yaml(src, {"title": "Grill", "views": [{"title": "Original"}]})

        with pytest.raises(click.ClickException):
            dashboard_ops.create_dashboard("dashboard-grill", str(src))

        types = _call_types(fake_ws)
        assert "lovelace/config/save" not in types
        assert "lovelace/dashboards/create" not in types


class TestCreateDashboardRollback:
    def test_failed_save_rolls_back_new_registration(self, tmp_path, monkeypatch, fake_ws, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []
        fake_ws._save_error = click.ClickException("save exploded")

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "New", "views": []})

        with pytest.raises(click.ClickException):
            dashboard_ops.create_dashboard("new-dash", str(src))

        # the half-created panel must not be left behind
        assert fake_ws._dashboards == []
        assert "lovelace/dashboards/delete" in _call_types(fake_ws)
        assert "rolled back panel registration" in capsys.readouterr().out

    def test_failed_save_does_not_delete_a_preexisting_panel(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        payload = {"title": "Grill", "views": []}
        fake_ws._live_config = dict(payload)
        fake_ws._dashboards = [{"id": "dashboard_grill", "url_path": "dashboard-grill"}]
        fake_ws._save_error = click.ClickException("save exploded")

        src = tmp_path / "grill.yaml"
        _write_yaml(src, payload)

        with pytest.raises(click.ClickException):
            dashboard_ops.create_dashboard("dashboard-grill", str(src))

        # we did not create it, so we must not delete it
        assert fake_ws._dashboards == [{"id": "dashboard_grill", "url_path": "dashboard-grill"}]
        assert "lovelace/dashboards/delete" not in _call_types(fake_ws)


class TestUpdateMissingDashboard:
    def test_update_of_unregistered_dashboard_suggests_create(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._live_config = None
        fake_ws._dashboards = []

        src = tmp_path / "new.yaml"
        _write_yaml(src, {"title": "New", "views": []})

        with pytest.raises(click.ClickException) as exc:
            dashboard_ops.update_dashboard("new-dash", str(src))

        msg = str(exc.value)
        assert "does not exist yet" in msg
        assert "--create" in msg
        assert "lovelace/config/save" not in _call_types(fake_ws)


class TestDeleteDashboard:
    def test_delete_removes_registration(self, tmp_path, monkeypatch, fake_ws, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._dashboards = [{"id": "scratch_dash", "url_path": "scratch-dash"}]

        dashboard_ops.delete_dashboard("scratch-dash")

        assert fake_ws._dashboards == []
        assert _call_kwargs(fake_ws, "lovelace/dashboards/delete") == {"dashboard_id": "scratch_dash"}
        assert "Deleted dashboard" in capsys.readouterr().out

    def test_delete_unregistered_dashboard_raises(self, tmp_path, monkeypatch, fake_ws):
        monkeypatch.setenv("HOME", str(tmp_path))
        fake_ws._dashboards = []

        with pytest.raises(click.ClickException) as exc:
            dashboard_ops.delete_dashboard("nope-dash")

        assert "not registered" in str(exc.value)
        assert "lovelace/dashboards/delete" not in _call_types(fake_ws)
