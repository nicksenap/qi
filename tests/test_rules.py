"""Tests for OpenAPI rules."""

from pathlib import Path

import yaml

from qi.rules import create_check_function, load_custom_rules

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_create_check_function():
    """Test creating check function from rule configuration."""
    rule_config = {
        "check": {
            "field": "required",
            "location": "/test/*/field",
        }
    }
    check_func = create_check_function(rule_config)

    # Test with valid spec
    spec = {"test": {"example": {"field": {"required": True}}}}
    errors = check_func(spec)
    assert not errors

    # Test with missing field
    spec = {"test": {"example": {"field": {}}}}
    errors = check_func(spec)
    assert len(errors) == 1
    assert errors[0] == "Missing required field 'required' at /test/example/field"


def test_create_check_function_wildcard():
    """Test check function with wildcard paths."""
    rule_config = {
        "check": {
            "field": "tags",
            "location": "/paths/*/get",
        }
    }
    check_func = create_check_function(rule_config)

    # Test with valid spec
    spec = {
        "paths": {
            "/users": {"get": {"tags": ["users"]}},
            "/orders": {"get": {"tags": ["orders"]}},
        }
    }
    errors = check_func(spec)
    assert not errors

    # Test with missing field
    spec = {
        "paths": {
            "/users": {"get": {}},
            "/orders": {"get": {"tags": ["orders"]}},
        }
    }
    errors = check_func(spec)
    assert len(errors) == 1
    assert errors[0] == "Missing required field 'tags' at /paths//users/get"


def test_load_custom_rules():
    """Test loading custom rules from YAML file."""
    config_data = {
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
    config_file = FIXTURES_DIR / "test_rules.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    try:
        rules = load_custom_rules(config_file)
        assert len(rules) == 1
        assert rules[0].name == "test-rule"
        assert rules[0].description == "Test rule"

        # Test the loaded rule
        spec = {"test": {"example": {"field": {"required": True}}}}
        errors = rules[0].check_func(spec)
        assert not errors
    finally:
        config_file.unlink(missing_ok=True)


def test_load_custom_rules_invalid_file():
    """Test loading custom rules from invalid file."""
    config_file = FIXTURES_DIR / "nonexistent.yaml"
    try:
        load_custom_rules(config_file)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "Failed to read or parse rules file" in str(e)


def test_load_custom_rules_invalid_format():
    """Test loading custom rules with invalid format."""
    config_data = {"invalid": "format"}
    config_file = FIXTURES_DIR / "invalid_rules.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    try:
        load_custom_rules(config_file)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "Rules file must contain an 'openapi-rules' list" in str(e)
    finally:
        config_file.unlink(missing_ok=True)


def test_load_custom_rules_missing_fields():
    """Test loading custom rules with missing required fields."""
    config_data = {
        "openapi-rules": [
            {
                "rule": "test-rule",
                # Missing description
                "check": {
                    "field": "required",
                    "location": "/test/*/field",
                },
            }
        ]
    }
    config_file = FIXTURES_DIR / "missing_fields.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    try:
        load_custom_rules(config_file)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "Invalid rule configuration, missing required field" in str(e)
    finally:
        config_file.unlink(missing_ok=True)
