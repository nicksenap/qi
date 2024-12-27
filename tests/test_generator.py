import os
import shutil
from pathlib import Path

import pytest
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
