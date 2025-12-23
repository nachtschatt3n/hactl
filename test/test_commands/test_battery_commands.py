"""
Tests for hactl BATTERY command group using Click's CliRunner
"""

import pytest
from click.testing import CliRunner
from hactl.cli import cli


class TestBatteryList:
    """Test hactl battery list command"""

    def test_battery_list_table(self, mock_env_vars, mock_api_request):
        """Test battery list in table format"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', 'list', '--format', 'table'])

        assert result.exit_code == 0
        assert 'sensor.battery_level' in result.output

    def test_battery_list_json(self, mock_env_vars, mock_api_request):
        """Test battery list in JSON format"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', 'list', '--format', 'json'])

        assert result.exit_code == 0
        assert '"entity_id"' in result.output

    def test_battery_list_exclude_mobile(self, mock_env_vars, mock_api_request):
        """Test battery list excluding mobile devices"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', 'list', '--exclude-mobile'])

        assert result.exit_code == 0

    def test_battery_list_include_mobile(self, mock_env_vars, mock_api_request):
        """Test battery list including mobile devices"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', 'list', '--include-mobile'])

        assert result.exit_code == 0


class TestBatteryCheck:
    """Test hactl battery check command"""

    def test_battery_check(self, mock_env_vars, mock_api_request):
        """Test battery check command"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', 'check'])

        assert result.exit_code == 0
        assert 'Battery Summary Sensors' in result.output or 'sensor.battery' in result.output.lower()


class TestBatteryMonitor:
    """Test hactl battery monitor command"""

    def test_battery_monitor_dry_run(self, mock_env_vars):
        """Test battery monitor in dry-run mode"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', 'monitor', '--dry-run'])

        assert result.exit_code == 0
        assert 'DRY RUN' in result.output or 'Battery Monitor Setup' in result.output

    def test_battery_monitor_normal(self, mock_env_vars):
        """Test battery monitor normal mode"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', 'monitor'])

        assert result.exit_code == 0


class TestBatteryHelp:
    """Test help output for battery commands"""

    def test_battery_help(self):
        """Test battery command group help"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', '--help'])

        assert result.exit_code == 0
        assert 'Battery monitoring utilities' in result.output
        assert 'list' in result.output
        assert 'check' in result.output

    def test_battery_list_help(self):
        """Test battery list help"""
        runner = CliRunner()
        result = runner.invoke(cli, ['battery', 'list', '--help'])

        assert result.exit_code == 0
        assert '--format' in result.output
