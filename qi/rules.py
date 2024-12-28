"""Rule configuration and management for OpenAPI linting."""

from pathlib import Path
from typing import Any

import yaml

from .linter import CustomRule


class RuleDefinition:
    """Definition of a custom rule that can be loaded from configuration."""

    def __init__(self, name: str, description: str, check: dict[str, str]):
        self.name = name
        self.description = description
        self.field = check.get("field", "")
        self.location = check.get("location", "")
        self.type = check.get("type", "required-field")


def check_path(spec: dict[str, Any], path_parts: list[str], pattern: str, current_path: str = "") -> list[str]:
    """Recursively check a path in the spec for a pattern."""
    if not path_parts:
        # We've reached the target path level, check for the pattern
        if not isinstance(spec, dict) or pattern not in spec:
            return [f"Missing required field '{pattern}' in {current_path}"]
        return []

    errors = []
    current = path_parts[0]
    remaining = path_parts[1:]

    if current == "*":
        if not isinstance(spec, dict):
            return []
        # For wildcards, check all children
        for key, value in spec.items():
            if value is not None:
                new_path = f"{current_path}/{key}" if current_path else key
                errors.extend(check_path(value, remaining, pattern, new_path))
    else:
        if not isinstance(spec, dict) or current not in spec:
            return []
        value = spec[current]
        if value is not None:
            new_path = f"{current_path}/{current}" if current_path else current
            errors.extend(check_path(value, remaining, pattern, new_path))

    return errors


def check_inline_models(spec: dict[str, Any], current_path: str = "") -> list[str]:
    """Check for inline models in the spec."""
    errors = []

    if isinstance(spec, dict):
        # Check if this is a schema definition
        if "type" in spec and spec["type"] == "object" and "properties" in spec:
            # This is an inline model
            if not current_path.startswith("/components/schemas"):
                errors.append(f"Inline model found at {current_path}")

        # Recursively check all children
        for key, value in spec.items():
            new_path = f"{current_path}/{key}" if current_path else key
            if isinstance(value, dict | list):
                errors.extend(check_inline_models(value, new_path))
    elif isinstance(spec, list):
        # Check array items
        for i, item in enumerate(spec):
            if isinstance(item, dict | list):
                errors.extend(check_inline_models(item, f"{current_path}[{i}]"))

    return errors


def create_rule_from_definition(rule_def: RuleDefinition) -> CustomRule:
    """Create a CustomRule from a RuleDefinition."""

    def check_func(spec: dict[str, Any]) -> list[str]:
        if rule_def.type == "no-inline-models":
            return check_inline_models(spec)

        # Regular field checking
        path_parts = [p for p in rule_def.location.split("/") if p]
        return check_path(spec, path_parts, rule_def.field)

    return CustomRule(
        name=rule_def.name,
        description=rule_def.description,
        check_func=check_func,
    )


def load_rules_from_config(config_path: Path) -> list[CustomRule]:
    """Load custom rules from a configuration file.

    The configuration file should be in YAML format with the following structure:
    ```yaml
    openapi-rules:
      - rule: my-rule
        description: My custom rule description
        check:
          type: required-field  # or no-inline-models
          field: required-field  # The field that must exist
          location: /paths/*/get  # Where to check for the field
    ```
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    rules = []
    for rule_config in config.get("openapi-rules", []):
        rule_def = RuleDefinition(
            name=rule_config["rule"],
            description=rule_config["description"],
            check=rule_config["check"],
        )
        rules.append(create_rule_from_definition(rule_def))

    return rules
