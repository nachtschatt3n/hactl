"""
Tests for hactl MEMORY command group using Click's CliRunner
"""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from hactl.cli import cli


class TestMemoryList:
    """Test hactl memory list command"""

    def test_memory_list(self, mock_env_vars):
        """Test memory list output"""
        runner = CliRunner()
        result = runner.invoke(cli, ['memory', 'list'])

        assert result.exit_code == 0
        assert 'Memory Contents:' in result.output


class TestMemoryAdd:
    """Test hactl memory add command"""

    def test_add_sensor_note(self, mock_env_vars, tmp_path, monkeypatch):
        """Test adding a note for a sensor"""
        # Use temporary directory for testing
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()

        # Patch MEMORY_DIR to use tmp_path
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        runner = CliRunner()
        result = runner.invoke(cli, [
            'memory', 'add',
            'sensor',
            'bedroom_temp',
            'Reads 2°C high'
        ])

        assert result.exit_code == 0
        assert 'Added note' in result.output

        # Verify note was saved
        notes_file = memory_dir / 'sensors' / 'notes.json'
        assert notes_file.exists()

        with open(notes_file, 'r') as f:
            notes = json.load(f)

        assert 'bedroom_temp' in notes
        assert notes['bedroom_temp'][0]['note'] == 'Reads 2°C high'

    def test_add_device_note(self, mock_env_vars, tmp_path, monkeypatch):
        """Test adding a note for a device"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        runner = CliRunner()
        result = runner.invoke(cli, [
            'memory', 'add',
            'device',
            'living_room_light',
            'Flickers when dimmed below 30%'
        ])

        assert result.exit_code == 0
        assert 'Added note' in result.output


class TestMemoryShow:
    """Test hactl memory show command"""

    def test_show_empty_category(self, mock_env_vars, tmp_path, monkeypatch):
        """Test showing notes for empty category"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ['memory', 'show', 'sensor'])

        assert result.exit_code == 0
        assert 'No notes found' in result.output

    def test_show_specific_item(self, mock_env_vars, tmp_path, monkeypatch):
        """Test showing notes for specific item"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()

        # Create a note first
        sensors_dir = memory_dir / 'sensors'
        sensors_dir.mkdir()
        notes_file = sensors_dir / 'notes.json'

        notes = {
            'bedroom_temp': [
                {'note': 'Test note', 'timestamp': '2024-01-01T12:00:00'}
            ]
        }

        with open(notes_file, 'w') as f:
            json.dump(notes, f)

        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ['memory', 'show', 'sensor', 'bedroom_temp'])

        assert result.exit_code == 0
        assert 'bedroom_temp' in result.output
        assert 'Test note' in result.output


class TestMemorySync:
    """Test hactl memory sync command"""

    def test_sync_all_categories(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test syncing all categories"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ['memory', 'sync'])

        assert result.exit_code == 0
        assert 'Syncing Home Assistant state' in result.output
        assert 'Memory sync complete' in result.output

    def test_sync_specific_category(self, mock_env_vars, mock_api_request, tmp_path, monkeypatch):
        """Test syncing specific category"""
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.memory_mgmt.MEMORY_DIR', memory_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ['memory', 'sync', '--category', 'sensors'])

        assert result.exit_code == 0
        assert 'sensors' in result.output.lower()


class TestMemoryHelp:
    """Test help output for memory commands"""

    def test_memory_help(self):
        """Test memory command group help"""
        runner = CliRunner()
        result = runner.invoke(cli, ['memory', '--help'])

        assert result.exit_code == 0
        assert 'AI memory and context management' in result.output
        assert 'add' in result.output
        assert 'show' in result.output
        assert 'sync' in result.output

    def test_memory_add_help(self):
        """Test memory add help"""
        runner = CliRunner()
        result = runner.invoke(cli, ['memory', 'add', '--help'])

        assert result.exit_code == 0
        assert 'Add contextual note' in result.output
