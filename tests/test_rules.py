"""Tests for OpenAPI rules."""

from pathlib import Path

import yaml

from qi.rules import (
    RuleDefinition,
    check_inline_models,
    check_path,
    create_rule_from_definition,
    load_rules_from_config,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_check_path_missing_field():
    """Test checking path with missing required field."""
    spec = {"test": {"nested": {}}}
    errors = check_path(spec, ["test", "nested"], "required_field", "")
    assert errors == ["Missing required field 'required_field' in test/nested"]


def test_check_path_wildcard():
    """Test checking path with wildcard."""
    spec = {
        "paths": {
            "/users": {"get": {"tags": ["users"]}},
            "/orders": {"get": {"tags": ["orders"]}},
        }
    }
    errors = check_path(spec, ["paths", "*", "get"], "tags", "")
    assert not errors


def test_check_path_wildcard_non_dict():
    """Test checking path with wildcard on non-dict."""
    spec = {"test": "not-a-dict"}
    errors = check_path(spec, ["test", "*"], "field", "")
    assert not errors


def test_check_path_missing_intermediate():
    """Test checking path with missing intermediate key."""
    spec = {"test": {}}
    errors = check_path(spec, ["test", "missing", "field"], "required", "")
    assert not errors


def test_check_path_none_value():
    """Test checking path with None value."""
    spec = {"test": {"nested": None}}
    errors = check_path(spec, ["test", "nested", "field"], "required", "")
    assert not errors


def test_check_inline_models_valid():
    """Test checking for inline models in valid location."""
    spec = {"components": {"schemas": {"User": {"$ref": "#/components/schemas/BaseModel"}}}}
    errors = check_inline_models(spec)
    assert not errors


def test_check_inline_models_invalid():
    """Test checking for inline models in invalid location."""
    spec = {
        "paths": {
            "/test": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                        },
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    errors = check_inline_models(spec)
    assert errors
    assert any("Inline model found at" in error for error in errors)


def test_check_inline_models_array():
    """Test checking for inline models in array."""
    spec = {
        "paths": {
            "/test": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": [
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string"},
                                                },
                                            }
                                        ],
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    errors = check_inline_models(spec)
    assert errors
    assert any("Inline model found at" in error for error in errors)


def test_create_rule_from_definition():
    """Test creating rule from definition."""
    # Create a rule that checks for the presence of a field named "required"
    rule_def = RuleDefinition(
        name="test-rule",
        description="Test rule",
        check={
            "type": "required-field",
            "field": "required",  # We want to check for a field named "required"
            "location": "test/*",  # Look for the "required" field in objects under test/*
        },
    )
    rule = create_rule_from_definition(rule_def)
    assert rule.name == "test-rule"
    assert rule.description == "Test rule"

    # Test the created rule with a spec that has the required field
    spec = {"test": {"example": {"required": True}}}  # The "required" field exists
    errors = rule.check_func(spec)
    assert not errors

    # Test with missing field
    spec = {"test": {"example": {}}}  # The "required" field is missing
    errors = rule.check_func(spec)
    assert len(errors) == 1
    assert errors[0] == "Missing required field 'required' in test/example"


def test_load_rules_from_config():
    """Test loading rules from config file."""
    config_data = {
        "openapi-rules": [
            {
                "rule": "test-rule",
                "description": "Test rule",
                "check": {
                    "type": "required-field",
                    "field": "required",
                    "location": "test/*/field",
                },
            }
        ]
    }
    config_file = FIXTURES_DIR / "test_rules.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    try:
        rules = load_rules_from_config(config_file)
        assert len(rules) == 1
        assert rules[0].name == "test-rule"
        assert rules[0].description == "Test rule"
    finally:
        config_file.unlink(missing_ok=True)
