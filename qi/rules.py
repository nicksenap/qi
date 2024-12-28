"""Rule configuration and management for OpenAPI linting."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .linter import CustomRule


def create_check_function(rule_config: dict[str, Any]) -> Callable[[dict[str, Any]], list[str]]:
    """Create a check function from a rule configuration."""
    check = rule_config["check"]
    field = check["field"]
    location = check["location"]

    def check_func(spec: dict[str, Any]) -> list[str]:
        errors = []
        # Split the location path into parts
        path_parts = [p for p in location.split("/") if p]

        def check_path(current: dict[str, Any], parts: list[str], current_path: str) -> None:
            if not parts:
                # We've reached the target location, check for the field
                if field not in current:
                    errors.append(f"Missing required field '{field}' at {current_path}")
                return

            part = parts[0]
            remaining_parts = parts[1:]

            if part == "*":
                # Wildcard - check all keys
                for key, value in current.items():
                    if isinstance(value, dict):
                        new_path = f"{current_path}/{key}"
                        check_path(value, remaining_parts, new_path)
            # Specific key
            elif part in current and isinstance(current[part], dict):
                new_path = f"{current_path}/{part}"
                check_path(current[part], remaining_parts, new_path)

        check_path(spec, path_parts, "")
        return errors

    return check_func


def load_custom_rules(rules_file: Path) -> list[CustomRule]:
    """Load custom rules from a YAML file.

    Args:
        rules_file: Path to the YAML file containing custom rules

    Returns:
        List of CustomRule objects

    Raises:
        ValueError: If the rules file is invalid
    """
    try:
        with open(rules_file) as f:
            rules_data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to read or parse rules file: {e}") from e

    if not isinstance(rules_data, dict) or "openapi-rules" not in rules_data:
        raise ValueError("Rules file must contain an 'openapi-rules' list")

    rules = []
    for rule_config in rules_data["openapi-rules"]:
        if not isinstance(rule_config, dict):
            continue

        try:
            rule = CustomRule(
                name=rule_config["rule"],
                description=rule_config["description"],
                check_func=create_check_function(rule_config),
            )
            rules.append(rule)
        except KeyError as e:
            raise ValueError(f"Invalid rule configuration, missing required field: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to create rule: {e}") from e

    return rules
