"""Tests for CLI functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
import yaml
from typer.testing import CliRunner

from qi.cli import app, validate_version

runner = CliRunner()
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_version():
    """Test version command."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Qi version" in result.stdout


def test_generate_command():
    """Test generate command."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.OpenAPIGenerator") as mock_generator:
        result = runner.invoke(app, ["generate", str(spec_file)])
        assert result.exit_code == 0
        mock_generator.return_value.generate_with_progress.assert_called_once()


def test_generate_command_with_config():
    """Test generate command with config file."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    config_file = FIXTURES_DIR / "test_config.yaml"

    # Create a test config file
    config_data = {
        "openapi_generator_version": "6.6.0",
        "java_package_base": "com.test",
        "model_package": "model",
        "api_package": "api",
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    try:
        with patch("qi.cli.Config") as mock_config, patch("qi.cli.OpenAPIGenerator") as mock_generator:
            mock_config.load.return_value = mock_config.default.return_value
            result = runner.invoke(app, ["generate", str(spec_file), "-c", str(config_file)])
            assert result.exit_code == 0
            mock_config.load.assert_called_once_with(str(config_file))
            mock_generator.assert_called_once_with(mock_config.load.return_value)
            mock_generator.return_value.generate_with_progress.assert_called_once()
    finally:
        config_file.unlink(missing_ok=True)


def test_generate_command_error():
    """Test generate command with error."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.OpenAPIGenerator") as mock_generator:
        mock_generator.return_value.generate_with_progress.side_effect = Exception("Test error")
        result = runner.invoke(app, ["generate", str(spec_file)])
        assert result.exit_code == 1
        assert "Error: Test error" in result.stdout


def test_convert_command():
    """Test convert command."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.OpenAPIGenerator") as mock_generator:
        result = runner.invoke(app, ["convert", str(spec_file), "--to", "3"])
        assert result.exit_code == 0
        mock_generator.return_value.convert_spec_version.assert_called_once()


def test_convert_command_with_output():
    """Test convert command with output file."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    output_file = "output.yaml"
    with patch("qi.cli.OpenAPIGenerator") as mock_generator:
        result = runner.invoke(app, ["convert", str(spec_file), "--to", "3", "-o", output_file])
        assert result.exit_code == 0
        mock_generator.return_value.convert_spec_version.assert_called_once()


def test_convert_command_error():
    """Test convert command with error."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.OpenAPIGenerator") as mock_generator:
        mock_generator.return_value.convert_spec_version.side_effect = Exception("Test error")
        result = runner.invoke(app, ["convert", str(spec_file), "--to", "3"])
        assert result.exit_code == 1
        assert "Error: Test error" in result.stdout


def test_validate_version_invalid():
    """Test validate_version with invalid version."""
    with pytest.raises(typer.BadParameter, match='Version must be either "2" or "3"'):
        validate_version("4")


def test_lint_command():
    """Test lint command."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.lint_specs", return_value=True) as mock_lint:
        result = runner.invoke(app, ["lint", str(spec_file)])
        assert result.exit_code == 0
        mock_lint.assert_called_once_with([Path(spec_file)], False)
        assert "All specifications are valid!" in result.stdout


def test_lint_command_verbose():
    """Test lint command with verbose flag."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.lint_specs", return_value=True) as mock_lint:
        result = runner.invoke(app, ["lint", "--verbose", str(spec_file)])
        assert result.exit_code == 0
        mock_lint.assert_called_once_with([Path(spec_file)], True)


def test_lint_command_invalid():
    """Test lint command with invalid specs."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.lint_specs", return_value=False) as mock_lint:
        result = runner.invoke(app, ["lint", str(spec_file)])
        assert result.exit_code == 1
        mock_lint.assert_called_once_with([Path(spec_file)], False)


def test_lint_command_error():
    """Test lint command with error."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.lint_specs", side_effect=Exception("Test error")) as mock_lint:
        result = runner.invoke(app, ["lint", str(spec_file)])
        assert result.exit_code == 1
        assert "Error: Test error" in result.stdout
        mock_lint.assert_called_once_with([Path(spec_file)], False)
