"""Tests for OpenAPI linter."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from qi.linter import LintingError, lint_spec, lint_specs

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_check_operation_tags():
    """Test operation tags validation."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    errors = lint_spec(spec_file)
    assert not any("must have at least one tag" in error for error in errors)


def test_check_operation_tags_missing():
    """Test operation tags validation with missing tags."""
    spec_data = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "summary": "Test endpoint",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_file = FIXTURES_DIR / "test_missing_tags.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_data, f)

    try:
        errors = lint_spec(spec_file)
        assert any("must have at least one tag" in error for error in errors)
    finally:
        spec_file.unlink(missing_ok=True)


def test_check_operation_ids():
    """Test operation IDs validation."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    errors = lint_spec(spec_file)
    assert not any("must have an operationId" in error for error in errors)


def test_check_operation_ids_missing():
    """Test operation IDs validation with missing operationId."""
    spec_data = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "summary": "Test endpoint",
                    "tags": ["test"],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_file = FIXTURES_DIR / "test_missing_ids.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_data, f)

    try:
        errors = lint_spec(spec_file)
        assert any("must have an operationId" in error for error in errors)
    finally:
        spec_file.unlink(missing_ok=True)


def test_lint_spec_invalid_file():
    """Test linting an invalid spec file."""
    with pytest.raises(LintingError, match="Failed to read or parse spec file"):
        lint_spec(Path("nonexistent.yaml"))


def test_lint_spec_invalid_reference():
    """Test linting a spec with invalid reference."""
    spec_data = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/NonExistent"}}}
                        }
                    }
                }
            }
        },
    }
    spec_file = FIXTURES_DIR / "test_invalid_ref.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_data, f)

    try:
        errors = lint_spec(spec_file)
        assert any("$ref" in error for error in errors)  # OpenAPI validator will catch invalid references
    finally:
        spec_file.unlink(missing_ok=True)


def test_lint_specs_verbose():
    """Test linting multiple specs with verbose output."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    with patch("qi.linter.console") as mock_console:
        lint_specs([spec_file], verbose=True)
        mock_console.print.assert_any_call(f"\nLinting [blue]{spec_file}[/blue]...")
        mock_console.print.assert_any_call(f"[green]✓[/green] {spec_file} is valid")


def test_lint_specs_with_errors():
    """Test linting multiple specs with errors."""
    spec_data = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "summary": "Test endpoint",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_file = FIXTURES_DIR / "test_with_errors.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_data, f)

    try:
        with patch("qi.linter.console") as mock_console:
            result = lint_specs([spec_file])
            assert not result
            mock_console.print.assert_any_call(f"[red]✗[/red] {spec_file} has validation errors:")
    finally:
        spec_file.unlink(missing_ok=True)


def test_lint_specs_with_linting_error():
    """Test linting multiple specs with linting error."""
    nonexistent_file = Path("nonexistent.yaml")
    with patch("qi.linter.console") as mock_console:
        result = lint_specs([nonexistent_file])
        assert not result
        error_msg = (
            f"[red]✗[/red] Error processing {nonexistent_file}: "
            "Failed to read or parse spec file: "
            "[Errno 2] No such file or directory: 'nonexistent.yaml'"
        )
        mock_console.print.assert_called_with(error_msg)
