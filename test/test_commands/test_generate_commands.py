"""
Tests for hactl GENERATE command group using Click's CliRunner
"""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from hactl.cli import cli


class TestGenerateDashboard:
    """Test hactl generate dashboard command"""

    def test_generate_dashboard_template(self, mock_env_vars, tmp_path, monkeypatch):
        """Test generating a dashboard with template"""
        generated_dir = tmp_path / 'generated'
        generated_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.ai_generator.GENERATED_DIR', generated_dir)

        # Create memory dir for context loading
        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.ai_generator.Path', lambda *args: memory_dir if 'memory' in str(args) else tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'dashboard', 'energy monitoring'])

        assert result.exit_code == 0
        assert 'Generated dashboard' in result.output

    def test_generate_dashboard_creates_manifest(self, mock_env_vars, tmp_path, monkeypatch):
        """Test that dashboard generation creates manifest"""
        generated_dir = tmp_path / 'generated'
        generated_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.ai_generator.GENERATED_DIR', generated_dir)

        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'dashboard', 'test dashboard'])

        assert result.exit_code == 0

        # Check manifest was created
        manifest_file = generated_dir / 'dashboards' / 'manifest.json'
        if manifest_file.exists():
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            assert 'files' in manifest


class TestGenerateAutomation:
    """Test hactl generate automation command"""

    def test_generate_automation(self, mock_env_vars, tmp_path, monkeypatch):
        """Test generating an automation"""
        generated_dir = tmp_path / 'generated'
        generated_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.ai_generator.GENERATED_DIR', generated_dir)

        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'automation', 'turn off lights after 10 minutes'])

        assert result.exit_code == 0
        assert 'Generated automation' in result.output


class TestGenerateBlueprint:
    """Test hactl generate blueprint command"""

    def test_generate_blueprint(self, mock_env_vars, tmp_path, monkeypatch):
        """Test generating a blueprint"""
        generated_dir = tmp_path / 'generated'
        generated_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.ai_generator.GENERATED_DIR', generated_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'blueprint', 'motion activated lights'])

        assert result.exit_code == 0
        assert 'Generated blueprint' in result.output


class TestGenerateScript:
    """Test hactl generate script command"""

    def test_generate_script(self, mock_env_vars, tmp_path, monkeypatch):
        """Test generating a script"""
        generated_dir = tmp_path / 'generated'
        generated_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.ai_generator.GENERATED_DIR', generated_dir)

        memory_dir = tmp_path / 'memory'
        memory_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'script', 'bedtime routine'])

        assert result.exit_code == 0
        assert 'Generated script' in result.output


class TestGenerateList:
    """Test hactl generate list command"""

    def test_list_empty_generated(self, mock_env_vars, tmp_path, monkeypatch):
        """Test listing when no content is generated"""
        generated_dir = tmp_path / 'generated'
        generated_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.ai_generator.GENERATED_DIR', generated_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'list'])

        assert result.exit_code == 0
        assert 'Generated Content:' in result.output

    def test_list_with_category_filter(self, mock_env_vars, tmp_path, monkeypatch):
        """Test listing with category filter"""
        generated_dir = tmp_path / 'generated'
        generated_dir.mkdir()
        monkeypatch.setattr('hactl.handlers.ai_generator.GENERATED_DIR', generated_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'list', '--category', 'dashboards'])

        assert result.exit_code == 0
        assert 'Dashboards:' in result.output


class TestGenerateApply:
    """Test hactl generate apply command"""

    def test_apply_nonexistent_file(self, mock_env_vars):
        """Test applying a file that doesn't exist"""
        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'apply', '/tmp/nonexistent.yaml'])

        assert result.exit_code != 0
        assert 'File not found' in result.output or 'Error' in result.output

    def test_apply_dashboard_file(self, mock_env_vars, tmp_path, monkeypatch):
        """Test applying a dashboard file"""
        # Create a fake dashboard file
        generated_dir = tmp_path / 'generated'
        dashboards_dir = generated_dir / 'dashboards'
        dashboards_dir.mkdir(parents=True)

        dashboard_file = dashboards_dir / 'test_dashboard.yaml'
        dashboard_file.write_text('title: Test Dashboard\nviews: []')

        # Create manifest
        manifest = {'files': [{'filename': 'test_dashboard.yaml', 'applied': False}]}
        with open(dashboards_dir / 'manifest.json', 'w') as f:
            json.dump(manifest, f)

        monkeypatch.setattr('hactl.handlers.ai_generator.GENERATED_DIR', generated_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'apply', str(dashboard_file)])

        assert result.exit_code == 0
        assert 'dashboard' in result.output.lower()


class TestGenerateHelp:
    """Test help output for generate commands"""

    def test_generate_help(self):
        """Test generate command group help"""
        runner = CliRunner()
        result = runner.invoke(cli, ['generate', '--help'])

        assert result.exit_code == 0
        assert 'AI-assisted generation' in result.output
        assert 'dashboard' in result.output
        assert 'automation' in result.output

    def test_generate_dashboard_help(self):
        """Test generate dashboard help"""
        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'dashboard', '--help'])

        assert result.exit_code == 0
        assert 'description' in result.output.lower()
