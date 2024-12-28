import os
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from apispec import APISpec
from rich.progress import Progress

from qi.config import Config
from qi.generator import OpenAPIGenerator


@pytest.fixture
def mock_progress():
    return Progress()


@pytest.fixture
def config():
    return Config.default()


@pytest.fixture
def generator(config):
    return OpenAPIGenerator(config)


@pytest.fixture
def spec_file(tmp_path):
    # Copy the test spec to a temporary location
    src = Path("tests/fixtures/test_spec.yaml")
    dst = tmp_path / "test_spec.yaml"
    shutil.copy2(src, dst)
    return dst


def test_parse_spec(generator, spec_file):
    """Test parsing OpenAPI specification."""
    spec_data = generator._parse_spec(str(spec_file))
    assert "components" in spec_data
    assert "schemas" in spec_data["components"]
    assert "User" in spec_data["components"]["schemas"]
    assert "Order" in spec_data["components"]["schemas"]


def test_get_custom_location(generator, spec_file):
    """Test extracting custom location from schema."""
    spec_data = generator._parse_spec(str(spec_file))

    # Test User schema location
    user_location = generator._get_custom_location("User", spec_data)
    assert user_location == "domain/user/model"

    # Test Order schema location
    order_location = generator._get_custom_location("Order", spec_data)
    assert order_location == "domain/order/model"

    # Test non-existent schema
    none_location = generator._get_custom_location("NonExistent", spec_data)
    assert none_location is None


def test_load_tracking(tmp_path, generator):
    """Test loading tracking data."""
    # Create test tracking file
    tracking_data = {"User": "domain/user/model/User.java", "Order": "domain/order/model/Order.java"}
    tracking_file = tmp_path / ".qi-tracking.yaml"
    with open(tracking_file, "w") as f:
        import yaml

        yaml.dump(tracking_data, f)

    # Set tracking file in generator
    generator.config.tracking_file = str(tracking_file)

    # Load and verify
    loaded_data = generator._load_tracking()
    assert loaded_data == tracking_data


def test_save_tracking(tmp_path, generator):
    """Test saving tracking data."""
    tracking_file = tmp_path / ".qi-tracking.yaml"
    generator.config.tracking_file = str(tracking_file)

    # Set some tracking data
    generator.tracking_data = {"User": "domain/user/model/User.java", "Order": "domain/order/model/Order.java"}

    # Save tracking data
    generator._save_tracking()

    # Verify saved data
    with open(tracking_file) as f:
        import yaml

        loaded_data = yaml.safe_load(f)

    assert loaded_data == generator.tracking_data


@pytest.mark.integration
def test_download_generator_with_progress(generator, mock_progress):
    """Test downloading OpenAPI generator."""
    task_id = mock_progress.add_task("Downloading...", total=None)
    jar_path = generator.download_generator_with_progress(mock_progress, task_id)

    assert os.path.exists(jar_path)
    assert jar_path.endswith(".jar")

    # Verify the jar is valid by checking its size
    assert os.path.getsize(jar_path) > 1000000  # Should be > 1MB


@pytest.mark.integration
def test_generate_with_progress(generator, mock_progress, spec_file, tmp_path):
    """Test generating code from specification with real OpenAPI Generator."""
    task_id = mock_progress.add_task("Generating...", total=None)
    output_dir = tmp_path / "generated"

    generator.generate_with_progress(str(spec_file), str(output_dir), mock_progress, task_id)

    # Verify User.java was generated in the correct location
    user_path = output_dir / "domain/user/model/User.java"
    assert user_path.exists()

    # Verify the content of the generated file
    with open(user_path) as f:
        content = f.read()
        assert "public class User" in content
        assert "private UUID id;" in content
        assert "private String name;" in content
        assert '@Schema(name = "id", description = "The user\'s unique identifier"' in content

    # Verify Order.java was generated in the correct location
    order_path = output_dir / "domain/order/model/Order.java"
    assert order_path.exists()

    # Verify the content of the generated file
    with open(order_path) as f:
        content = f.read()
        assert "public class Order" in content
        assert "private UUID id;" in content
        assert "private UUID userId;" in content
        assert '@Schema(name = "userId", description = "The ID of the user who placed the order"' in content


def test_convert_spec_version_2_to_3(tmp_path):
    # Create a mock OpenAPI 2.0 spec
    spec_v2 = {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {},
        "definitions": {"User": {"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}}}},
    }
    input_file = tmp_path / "input.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v2, f)

    config = Config.default()
    generator = OpenAPIGenerator(config)
    output_file = generator.convert_spec_version(str(input_file), "3")

    # Verify the output
    assert os.path.exists(output_file)
    with open(output_file) as f:
        converted_spec = yaml.safe_load(f)
    assert converted_spec["openapi"] == "3.0.0"
    assert "components" in converted_spec
    assert "schemas" in converted_spec["components"]
    assert "User" in converted_spec["components"]["schemas"]


def test_convert_spec_version_3_to_2(tmp_path):
    # Create a mock OpenAPI 3.0 spec
    spec_v3 = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {},
        "components": {
            "schemas": {"User": {"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}}}}
        },
    }
    input_file = tmp_path / "input.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v3, f)

    config = Config.default()
    generator = OpenAPIGenerator(config)
    output_file = generator.convert_spec_version(str(input_file), "2")

    # Verify the output
    assert os.path.exists(output_file)
    with open(output_file) as f:
        converted_spec = yaml.safe_load(f)
    assert converted_spec["swagger"] == "2.0"
    assert "definitions" in converted_spec
    assert "User" in converted_spec["definitions"]


def test_convert_spec_version_same_version(tmp_path):
    # Create a mock OpenAPI 3.0 spec
    spec_v3 = {"openapi": "3.0.0", "info": {"title": "Test API", "version": "1.0.0"}, "paths": {}}
    input_file = tmp_path / "input.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v3, f)

    config = Config.default()
    generator = OpenAPIGenerator(config)
    output_file = generator.convert_spec_version(str(input_file), "3")

    # Should return the input file without conversion
    assert os.path.exists(output_file)
    with open(output_file) as f:
        converted_spec = yaml.safe_load(f)
    assert converted_spec["openapi"] == "3.0.0"


def test_convert_spec_version_with_progress(tmp_path):
    # Create a mock OpenAPI 2.0 spec
    spec_v2 = {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {},
        "definitions": {"User": {"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}}}},
    }
    input_file = tmp_path / "input.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v2, f)

    config = Config.default()
    generator = OpenAPIGenerator(config)
    progress = Progress()
    task_id = progress.add_task("Converting...", total=None)

    output_file = generator.convert_spec_version(str(input_file), "3", progress=progress, task_id=task_id)

    assert os.path.exists(output_file)
    with open(output_file) as f:
        converted_spec = yaml.safe_load(f)
    assert converted_spec["openapi"] == "3.0.0"
    assert "components" in converted_spec
    assert "schemas" in converted_spec["components"]
    assert "User" in converted_spec["components"]["schemas"]


def test_convert_schemas_2_to_3(generator):
    """Test schema conversion from OpenAPI 2.0 to 3.0."""
    spec_data = {
        "swagger": "2.0",
        "definitions": {"User": {"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}}}},
    }
    spec = APISpec(
        title="Test API",
        version="1.0.0",
        openapi_version="3.0.0",
    )

    generator._convert_schemas(spec_data, "3", spec)
    result = spec.to_dict()

    assert "components" in result
    assert "schemas" in result["components"]
    assert "User" in result["components"]["schemas"]


def test_convert_schemas_3_to_2(generator):
    """Test schema conversion from OpenAPI 3.0 to 2.0."""
    spec_data = {
        "openapi": "3.0.0",
        "components": {
            "schemas": {"User": {"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}}}}
        },
    }
    spec = APISpec(
        title="Test API",
        version="1.0.0",
        openapi_version="2.0",
    )

    generator._convert_schemas(spec_data, "2", spec)
    result = spec.to_dict()

    assert "definitions" in result
    assert "User" in result["definitions"]


def test_convert_spec_version_no_schemas(tmp_path, generator):
    """Test conversion of spec without schemas."""
    spec_v2 = {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {"/test": {"get": {"responses": {"200": {"description": "OK"}}}}},
    }
    input_file = tmp_path / "input.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v2, f)

    output_file = generator.convert_spec_version(str(input_file), "3")

    with open(output_file) as f:
        converted_spec = yaml.safe_load(f)
    assert converted_spec["openapi"] == "3.0.0"
    assert "paths" in converted_spec
    assert "/test" in converted_spec["paths"]


def test_convert_spec_version_empty_spec(tmp_path, generator):
    """Test conversion of empty spec."""
    spec_v2 = {"swagger": "2.0", "info": {"title": "Test API", "version": "1.0.0"}}
    input_file = tmp_path / "input.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v2, f)

    output_file = generator.convert_spec_version(str(input_file), "3")

    with open(output_file) as f:
        converted_spec = yaml.safe_load(f)
    assert converted_spec["openapi"] == "3.0.0"
    assert "info" in converted_spec


def test_convert_spec_version_with_output_file(tmp_path, generator):
    """Test conversion with specified output file."""
    spec_v2 = {"swagger": "2.0", "info": {"title": "Test API", "version": "1.0.0"}}
    input_file = tmp_path / "input.yaml"
    output_file = tmp_path / "output.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v2, f)

    result = generator.convert_spec_version(str(input_file), "3", str(output_file))
    assert result == str(output_file)
    assert os.path.exists(output_file)


def test_convert_spec_version_same_version_with_output(tmp_path, generator):
    """Test same version conversion with output file."""
    spec_v3 = {"openapi": "3.0.0", "info": {"title": "Test API", "version": "1.0.0"}}
    input_file = tmp_path / "input.yaml"
    output_file = tmp_path / "output.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v3, f)

    result = generator.convert_spec_version(str(input_file), "3", str(output_file))
    assert result == str(output_file)
    assert os.path.exists(output_file)
    with open(output_file) as f:
        content = yaml.safe_load(f)
        assert content == spec_v3


def test_convert_spec_version_invalid_spec(tmp_path, generator):
    """Test conversion with invalid spec file."""
    input_file = tmp_path / "input.yaml"
    with open(input_file, "w") as f:
        f.write("invalid: yaml: content")

    with pytest.raises(yaml.YAMLError):
        generator.convert_spec_version(str(input_file), "3")


def test_convert_spec_version_with_progress_updates(tmp_path, generator):
    """Test that progress updates are called correctly."""

    spec_v2 = {"swagger": "2.0", "info": {"title": "Test API", "version": "1.0.0"}}
    input_file = tmp_path / "input.yaml"
    with open(input_file, "w") as f:
        yaml.dump(spec_v2, f)

    progress = Mock(spec=Progress)
    task_id = "test_task"

    generator.convert_spec_version(str(input_file), "3", progress=progress, task_id=task_id)

    # Verify progress updates
    assert progress.update.call_count >= 2  # At least start and end updates

    # Check for specific progress messages
    calls = [call.kwargs.get("description", "") for call in progress.update.call_args_list]
    assert any("Converting specification" in str(desc) for desc in calls)
    assert any("Conversion completed" in str(desc) for desc in calls)
