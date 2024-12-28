from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from openapi_spec_validator.validation.validators import OpenAPIV30SpecValidator
from referencing.exceptions import PointerToNowhere
from rich.console import Console

console = Console()


class LintingError(Exception):
    """Custom exception for linting errors."""

    pass


class CustomRule:
    """A custom linting rule for OpenAPI specs."""

    def __init__(self, name: str, description: str, check_func: Callable[[dict[str, Any]], list[str]]):
        self.name = name
        self.description = description
        self.check_func = check_func


def check_operation_tags(spec: dict[str, Any]) -> list[str]:
    """Check that all operations have tags."""
    errors = []
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                continue
            if not operation.get("tags"):
                errors.append(f"Operation {method.upper()} {path} must have at least one tag")

    return errors


def check_operation_ids(spec: dict[str, Any]) -> list[str]:
    """Check that all operations have operationId."""
    errors = []
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                continue
            if not operation.get("operationId"):
                errors.append(f"Operation {method.upper()} {path} must have an operationId")

    return errors


# Default custom rules
DEFAULT_RULES = [
    CustomRule(
        "operation-tags",
        "All operations must have at least one tag",
        check_operation_tags,
    ),
    CustomRule(
        "operation-ids",
        "All operations must have an operationId",
        check_operation_ids,
    ),
]


def lint_spec(spec_path: Path, custom_rules: list[CustomRule] = DEFAULT_RULES) -> list[str]:
    """Lint an OpenAPI specification file.

    Args:
        spec_path: Path to the OpenAPI specification file
        custom_rules: List of custom rules to apply (defaults to DEFAULT_RULES)

    Returns:
        List of validation errors if any

    Raises:
        LintingError: If the file cannot be read or parsed
    """
    try:
        with open(spec_path) as f:
            spec_dict = yaml.safe_load(f)
    except Exception as e:
        raise LintingError(f"Failed to read or parse spec file: {e}") from e

    errors = []

    # Run OpenAPI schema validation
    validator = OpenAPIV30SpecValidator(spec_dict)
    try:
        for error in validator.iter_errors():
            errors.append(str(error))
    except PointerToNowhere as e:
        errors.append(f"Invalid reference: {e}")

    # Run custom rules
    for rule in custom_rules:
        rule_errors = rule.check_func(spec_dict)
        for error in rule_errors:
            errors.append(f"{rule.name}: {error}")

    return errors


def lint_specs(spec_paths: list[Path], verbose: bool = False, custom_rules: list[CustomRule] = DEFAULT_RULES) -> bool:
    """Lint multiple OpenAPI specification files.

    Args:
        spec_paths: List of paths to OpenAPI specification files
        verbose: Whether to print detailed error messages
        custom_rules: List of custom rules to apply (defaults to DEFAULT_RULES)

    Returns:
        True if all specs are valid, False otherwise
    """
    all_valid = True

    for spec_path in spec_paths:
        if verbose:
            console.print(f"\nLinting [blue]{spec_path}[/blue]...")

        try:
            errors = lint_spec(spec_path, custom_rules)
            if errors:
                all_valid = False
                console.print(f"[red]✗[/red] {spec_path} has validation errors:")
                for error in errors:
                    console.print(f"  [red]•[/red] {error}")
            elif verbose:
                console.print(f"[green]✓[/green] {spec_path} is valid")
        except LintingError as e:
            all_valid = False
            console.print(f"[red]✗[/red] Error processing {spec_path}: {e!s}")

    return all_valid
