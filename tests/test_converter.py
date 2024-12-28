"""Tests for OpenAPI specification converter."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from apispec import APISpec

from qi.converter import OpenAPIConverter

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def converter():
    """Create a converter instance."""
    return OpenAPIConverter()


def test_convert_schemas():
    """Test schema conversion."""
    spec_data = {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "format": "uuid"}},
                }
            }
        }
    }
    spec = APISpec(title="Test API", version="1.0.0", openapi_version="3.0.0")
    OpenAPIConverter._convert_schemas(spec_data, "3", spec)

    # Add schema to spec
    for name, schema in spec_data["components"]["schemas"].items():
        spec.components.schema(name, schema)

    converted = spec.to_dict()
    assert "components" in converted
    assert "schemas" in converted["components"]
    assert "User" in converted["components"]["schemas"]


def test_convert_schemas_v2():
    """Test schema conversion from OpenAPI 2.0."""
    spec_data = {
        "definitions": {
            "User": {
                "type": "object",
                "properties": {"id": {"type": "string", "format": "uuid"}},
            }
        }
    }
    spec = APISpec(title="Test API", version="1.0.0", openapi_version="3.0.0")
    OpenAPIConverter._convert_schemas(spec_data, "3", spec)
    converted = spec.to_dict()
    assert "components" in converted
    assert "schemas" in converted["components"]
    assert "User" in converted["components"]["schemas"]


def test_convert_spec_same_version(converter, tmp_path):
    """Test converting spec to same version."""
    spec_data = {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0.0"},
    }
    spec_file = tmp_path / "test_spec.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_data, f)

    # Test with progress
    progress = MagicMock()
    task_id = 1
    result = converter.convert_spec(spec_file, "2", progress=progress, task_id=task_id)
    assert result == spec_file
    progress.update.assert_called_with(task_id, description="[green]Specification already in target version")

    # Test with output file
    output_file = tmp_path / "output.yaml"
    result = converter.convert_spec(spec_file, "2", output_file=output_file)
    assert result == output_file
    assert output_file.exists()
    with open(output_file) as f:
        assert yaml.safe_load(f) == spec_data


def test_convert_spec_2_to_3(converter, tmp_path):
    """Test converting from OpenAPI 2.0 to 3.0."""
    spec_data = {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get users",
                    "responses": {"200": {"description": "Success"}},
                }
            }
        },
        "definitions": {
            "User": {
                "type": "object",
                "properties": {"id": {"type": "string", "format": "uuid"}},
            }
        },
    }
    spec_file = tmp_path / "test_spec.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_data, f)

    # Test with progress
    progress = MagicMock()
    task_id = 1
    result = converter.convert_spec(spec_file, "3", progress=progress, task_id=task_id)

    assert result.exists()
    with open(result) as f:
        converted = yaml.safe_load(f)
        assert "openapi" in converted
        assert converted["openapi"].startswith("3")
        assert "components" in converted
        assert "schemas" in converted["components"]
        assert "User" in converted["components"]["schemas"]

    # Verify progress updates
    progress.update.assert_any_call(task_id, description="[yellow]Converting specification to version 3...")
    progress.update.assert_any_call(task_id, description="[green]Conversion completed!")


def test_convert_spec_3_to_2(converter, tmp_path):
    """Test converting from OpenAPI 3.0 to 2.0."""
    spec_data = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get users",
                    "responses": {"200": {"description": "Success"}},
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "format": "uuid"}},
                }
            }
        },
    }
    spec_file = tmp_path / "test_spec.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_data, f)

    result = converter.convert_spec(spec_file, "2")

    assert result.exists()
    with open(result) as f:
        converted = yaml.safe_load(f)
        assert "swagger" in converted
        assert converted["swagger"] == "2.0"
        assert "definitions" in converted
        assert "User" in converted["definitions"]
        assert "components" not in converted


def test_convert_spec_with_output_file(converter, tmp_path):
    """Test converting spec with custom output file."""
    spec_data = {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0.0"},
    }
    spec_file = tmp_path / "test_spec.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_data, f)

    output_file = tmp_path / "output.yaml"
    result = converter.convert_spec(spec_file, "3", output_file=output_file)

    assert result == output_file
    assert output_file.exists()
    with open(output_file) as f:
        converted = yaml.safe_load(f)
        assert "openapi" in converted
        assert converted["openapi"].startswith("3")
