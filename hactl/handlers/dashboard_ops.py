"""
Dashboard update operations handler.

Adds backup-before-overwrite and drift detection so a dashboard push can never
silently clobber UI edits made directly in the Home Assistant frontend.
"""

import datetime
import io
import json
import os
from pathlib import Path

import click

from hactl.core import load_config
from hactl.core.formatting import json_to_yaml
from hactl.core.websocket import WebSocketClient

# Try to import yaml, but make it optional
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None


# Fields that the HA backend may inject or rewrite. We ignore these when
# deciding whether the live config has drifted from the on-disk source.
_TRIVIAL_TOP_LEVEL_KEYS = frozenset({"version"})


def _backup_dir() -> Path:
    """Return ~/.hactl/backups, creating it if missing."""
    base = Path(os.path.expanduser("~/.hactl/backups"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_yaml_file(yaml_file):
    """Load YAML file and convert to dict."""
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            if HAS_YAML:
                try:
                    return yaml.safe_load(f)
                except Exception:
                    pass
            # Fallback to JSON
            f.seek(0)
            return json.load(f)
    except FileNotFoundError:
        raise click.ClickException(f"File not found: {yaml_file}")
    except Exception as e:
        raise click.ClickException(f"Error loading file: {e}")


def _dump_yaml(obj) -> str:
    """Dump a dict to YAML in roughly the same shape ``hactl generate`` uses.

    Falls back to the in-house ``json_to_yaml`` if PyYAML is not installed,
    which guarantees something restorable even on minimal installs.
    """
    if HAS_YAML:
        return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return json_to_yaml(obj)


def _utc_timestamp() -> str:
    """RFC3339-ish timestamp safe for filenames."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _unique_backup_path(slug: str, ts: str) -> Path:
    """Return a non-existing backup path; suffix ``-2``, ``-3`` etc on collision."""
    base = _backup_dir()
    candidate = base / f"dashboard_{slug}_{ts}.yaml"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = base / f"dashboard_{slug}_{ts}-{n}.yaml"
        if not candidate.exists():
            return candidate
        n += 1


def _normalize_for_diff(obj):
    """Return a comparable representation that ignores HA-injected metadata.

    Rules:
      * drop the top-level ``version`` key (HA stamps this on writes)
      * drop ``None`` values everywhere (PyYAML round-trip can introduce them)
      * recurse into dicts and lists; preserve list ordering (semantically meaningful in lovelace)
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _TRIVIAL_TOP_LEVEL_KEYS:
                continue
            if v is None:
                continue
            out[k] = _normalize_for_diff(v)
        return out
    if isinstance(obj, list):
        return [_normalize_for_diff(v) for v in obj]
    return obj


def _configs_equivalent(live, on_disk) -> bool:
    """True when the two configs match modulo HA-injected trivia."""
    return _normalize_for_diff(live) == _normalize_for_diff(on_disk)


def _unified_diff(live, on_disk, source_path: str, max_lines: int = 30) -> str:
    """Return a short unified diff between the live and on-disk configs."""
    import difflib

    live_text = _dump_yaml(_normalize_for_diff(live)).splitlines()
    disk_text = _dump_yaml(_normalize_for_diff(on_disk)).splitlines()
    diff = list(difflib.unified_diff(
        disk_text,
        live_text,
        fromfile=source_path,
        tofile="live",
        lineterm="",
    ))
    if len(diff) > max_lines:
        diff = diff[:max_lines] + [f"... ({len(diff) - max_lines} more lines truncated)"]
    return "\n".join(diff)


def _fetch_live_config(ws: WebSocketClient, url_path: str):
    """Fetch the current live lovelace config for ``url_path`` over WebSocket.

    Returns ``None`` if the dashboard does not yet exist (create flow).
    """
    try:
        return ws.call("lovelace/config", url_path=url_path)
    except click.ClickException as err:
        msg = str(err).lower()
        if "config_not_found" in msg or "not found" in msg:
            return None
        raise


def _write_backup(slug: str, live_config) -> Path:
    """Persist ``live_config`` to disk under ~/.hactl/backups/. Returns the path."""
    ts = _utc_timestamp()
    path = _unique_backup_path(slug, ts)
    path.write_text(_dump_yaml(live_config), encoding="utf-8")
    return path


def update_dashboard(url_path, yaml_file, force: bool = False):
    """Update an existing dashboard, with backup + drift detection.

    Args:
        url_path: lovelace url_path of the dashboard (e.g. ``battery-monitor``).
        yaml_file: path to the YAML file holding the new config.
        force: if True, skip the drift check (backup is still taken).
    """
    HASS_URL, HASS_TOKEN = load_config()
    new_config = load_yaml_file(yaml_file)

    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()

        # Step 1: fetch live config and back it up before doing anything destructive.
        live_config = _fetch_live_config(ws, url_path)
        backup_path = None
        if live_config is not None:
            backup_path = _write_backup(url_path, live_config)
            click.echo(f"backup: {backup_path}")

        # Step 2: drift detection (default-on).
        if live_config is not None and not force:
            if not _configs_equivalent(live_config, new_config):
                diff_text = _unified_diff(live_config, new_config, yaml_file)
                lines = [
                    f"error: live dashboard '{url_path}' has diverged from {yaml_file}.",
                    f"live -> backed up to {backup_path}",
                    "diff:",
                    diff_text,
                    "to overwrite anyway: re-run with --force",
                    f"to merge: hactl pull dashboard {url_path} --to {yaml_file} first, then update.",
                ]
                raise click.ClickException("\n".join(lines))

        # Step 3: actually push.
        ws.call("lovelace/config/save", url_path=url_path, config=new_config)
        click.secho(f"✓ Successfully updated dashboard: {url_path}", fg='green')
    finally:
        ws.close()


def create_dashboard(url_path, yaml_file, force: bool = False):
    """Create a new dashboard.

    If a dashboard already exists at ``url_path`` we treat it like an update:
    take a backup and apply drift detection unless ``force`` is set.
    """
    HASS_URL, HASS_TOKEN = load_config()
    new_config = load_yaml_file(yaml_file)

    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()

        live_config = _fetch_live_config(ws, url_path)
        if live_config is not None:
            backup_path = _write_backup(url_path, live_config)
            click.echo(f"backup: {backup_path}")
            if not force and not _configs_equivalent(live_config, new_config):
                diff_text = _unified_diff(live_config, new_config, yaml_file)
                lines = [
                    f"error: dashboard '{url_path}' already exists and has diverged from {yaml_file}.",
                    f"live -> backed up to {backup_path}",
                    "diff:",
                    diff_text,
                    "to overwrite anyway: re-run with --force",
                ]
                raise click.ClickException("\n".join(lines))

        ws.call("lovelace/config/save", url_path=url_path, config=new_config)
        click.secho(f"✓ Successfully created dashboard: {url_path}", fg='green')
    finally:
        ws.close()


def pull_dashboard(url_path: str, to_path: str) -> Path:
    """Fetch the live lovelace config for ``url_path`` and write it to ``to_path``.

    Recovery path referenced in the drift-blocked error message.
    """
    HASS_URL, HASS_TOKEN = load_config()
    ws = WebSocketClient(HASS_URL, HASS_TOKEN)
    try:
        ws.connect()
        live_config = _fetch_live_config(ws, url_path)
        if live_config is None:
            raise click.ClickException(f"dashboard '{url_path}' not found on the server")
    finally:
        ws.close()

    out = Path(to_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_dump_yaml(live_config), encoding="utf-8")
    click.secho(f"✓ Pulled dashboard '{url_path}' to {out}", fg='green')
    return out
