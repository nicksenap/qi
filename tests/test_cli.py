"""Tests for CLI functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
import yaml
from typer.testing import CliRunner

from qi.cli import app, validate_version
from qi.linter import DEFAULT_RULES

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
        mock_lint.assert_called_once_with([Path(spec_file)], False, custom_rules=DEFAULT_RULES)
        assert "All specifications are valid!" in result.stdout


def test_lint_command_verbose():
    """Test lint command with verbose flag."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.lint_specs", return_value=True) as mock_lint:
        result = runner.invoke(app, ["lint", "--verbose", str(spec_file)])
        assert result.exit_code == 0
        mock_lint.assert_called_once_with([Path(spec_file)], True, custom_rules=DEFAULT_RULES)


def test_lint_command_invalid():
    """Test lint command with invalid specs."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.lint_specs", return_value=False) as mock_lint:
        result = runner.invoke(app, ["lint", str(spec_file)])
        assert result.exit_code == 1
        mock_lint.assert_called_once_with([Path(spec_file)], False, custom_rules=DEFAULT_RULES)


def test_lint_command_error():
    """Test lint command with error."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.lint_specs", side_effect=Exception("Test error")) as mock_lint:
        result = runner.invoke(app, ["lint", str(spec_file)])
        assert result.exit_code == 1
        assert "Error: Test error" in result.stdout
        mock_lint.assert_called_once_with([Path(spec_file)], False, custom_rules=DEFAULT_RULES)


def test_lint_command_with_rules():
    """Test lint command with custom rules file."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    rules_file = FIXTURES_DIR / "test_rules.yaml"

    # Create a test rules file
    rules_data = {
        "openapi-rules": [
            {
                "rule": "test-rule",
                "description": "Test rule",
                "check": {
                    "field": "required",
                    "location": "/test/*/field",
                },
            }
        ]
    }
    with open(rules_file, "w") as f:
        yaml.dump(rules_data, f)

    try:
        with patch("qi.cli.lint_specs", return_value=True) as mock_lint:
            result = runner.invoke(app, ["lint", "--rules", str(rules_file), str(spec_file)])
            assert result.exit_code == 0

            # The rules should have been loaded and passed to lint_specs
            mock_lint.assert_called_once()
            call_args = mock_lint.call_args
            assert call_args[0][0] == [Path(spec_file)]  # First positional arg (spec_files)
            assert call_args[0][1] is False  # Second positional arg (verbose)

            # Verify the loaded rules
            custom_rules = call_args[1]["custom_rules"]
            assert len(custom_rules) == 1
            assert custom_rules[0].name == "test-rule"
            assert custom_rules[0].description == "Test rule"

            assert "All specifications are valid!" in result.stdout
    finally:
        rules_file.unlink(missing_ok=True)


def test_lint_command_with_invalid_rules():
    """Test lint command with invalid rules file."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    rules_file = FIXTURES_DIR / "invalid_rules.yaml"

    # Create an invalid rules file
    with open(rules_file, "w") as f:
        yaml.dump({"invalid": "format"}, f)

    try:
        with patch("qi.cli.load_custom_rules") as mock_load_rules:
            mock_load_rules.side_effect = ValueError("Invalid rules file")
            result = runner.invoke(app, ["lint", "--rules", str(rules_file), str(spec_file)])
            assert result.exit_code == 1
            assert "Error: Invalid rules file" in result.stdout
    finally:
        rules_file.unlink(missing_ok=True)


def test_lint_command_no_rules_file():
    """Test lint command without a rules file uses DEFAULT_RULES."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.cli.lint_specs", return_value=True) as mock_lint:
        result = runner.invoke(app, ["lint", str(spec_file)])
        assert result.exit_code == 0

        # Verify that DEFAULT_RULES are used when no rules file is provided
        mock_lint.assert_called_once()
        call_args = mock_lint.call_args
        assert call_args[0][0] == [Path(spec_file)]  # First positional arg (spec_files)
        assert call_args[0][1] is False  # Second positional arg (verbose)
        assert call_args[1]["custom_rules"] == DEFAULT_RULES

        assert "All specifications are valid!" in result.stdout
