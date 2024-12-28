"""Tests for OpenAPI code generator."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from qi.config import Config
from qi.generator import OpenAPIGenerator

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def generator():
    """Create a generator instance with default config."""
    config = Config.default()
    return OpenAPIGenerator(config)


def test_load_tracking_empty_file(generator, tmp_path):
    """Test loading tracking data from empty file."""
    tracking_file = tmp_path / ".qi-tracking.yaml"
    with open(tracking_file, "w") as f:
        f.write("")  # Empty file

    generator.config.tracking_file = str(tracking_file)
    loaded_data = generator._load_tracking()
    assert loaded_data == {}


def test_load_tracking(generator, tmp_path):
    """Test loading tracking data."""
    tracking_file = tmp_path / ".qi-tracking.yaml"
    tracking_data = {"User": "path/to/User.java"}
    with open(tracking_file, "w") as f:
        yaml.dump(tracking_data, f)

    generator.config.tracking_file = str(tracking_file)
    loaded_data = generator._load_tracking()
    assert loaded_data == tracking_data


def test_save_tracking(generator, tmp_path):
    """Test saving tracking data."""
    tracking_file = tmp_path / ".qi-tracking.yaml"
    generator.config.tracking_file = str(tracking_file)
    generator.tracking_data = {"User": "path/to/User.java"}

    generator._save_tracking()
    assert tracking_file.exists()

    with open(tracking_file) as f:
        loaded_data = yaml.safe_load(f)
    assert loaded_data == generator.tracking_data


def test_download_generator(generator):
    """Test downloading OpenAPI Generator CLI."""
    jar_name = f"openapi-generator-cli-{generator.config.openapi_generator_version}.jar"

    # Mock the requests.get call
    mock_response = MagicMock()
    mock_response.headers = {"content-length": "1024"}
    mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]

    # Create a mock progress object with proper setup
    progress = MagicMock()
    task_id = 1

    with (
        patch("requests.get", return_value=mock_response),
        patch("builtins.open", create=True),
        patch("os.path.exists", return_value=False),
    ):  # Simulate jar doesn't exist
        result = generator.download_generator_with_progress(progress, task_id)
        assert result == jar_name

        # Verify progress updates
        progress.update.assert_called()
        progress.start_task.assert_called_once_with(task_id)


def test_parse_spec(generator):
    """Test parsing OpenAPI specification."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    spec_data = generator._parse_spec(str(spec_file))
    assert "openapi" in spec_data
    assert "paths" in spec_data
    assert "components" in spec_data


def test_get_custom_location(generator):
    """Test getting custom location from x-qi-dir."""
    spec_data = {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "x-qi-dir": "domain/user/model",
                },
            },
        },
    }

    location = generator._get_custom_location("User", spec_data)
    assert location == "domain/user/model"

    # Test non-existent schema
    location = generator._get_custom_location("NonExistent", spec_data)
    assert location is None


@pytest.mark.integration
def test_generate_with_progress(generator, tmp_path):
    """Test code generation with progress reporting."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    output_dir = tmp_path / "generated"
    temp_dir = "temp_generated"
    model_dir = os.path.join(
        temp_dir, "src/main/java", generator.config.java_package_base.replace(".", "/"), generator.config.model_package
    )

    # Create test spec data with custom location
    spec_data = {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "x-qi-dir": "domain/user/model",
                },
                "Order": {
                    "type": "object",
                },
            },
        },
    }

    progress = MagicMock()
    task_id = 1

    with (
        patch("subprocess.run") as mock_run,
        patch("os.makedirs") as mock_makedirs,
        patch("os.listdir") as mock_listdir,
        patch("shutil.copy2") as mock_copy2,
        patch("shutil.rmtree") as mock_rmtree,
        patch.object(generator, "_parse_spec", return_value=spec_data),
        patch("os.path.exists", return_value=True),  # Simulate file exists for coverage
    ):
        # Setup mocks
        mock_listdir.return_value = ["User.java", "Order.java"]

        # Run the generator
        generator.generate_with_progress(str(spec_file), str(output_dir), progress, task_id)

        # Verify progress updates
        progress.update.assert_called()

        # Verify subprocess call
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert "generate" in cmd_args
        assert "-g" in cmd_args
        assert "spring" in cmd_args

        # Verify directory creation
        mock_makedirs.assert_any_call(temp_dir, exist_ok=True)

        # Verify file operations
        mock_listdir.assert_called_once_with(model_dir)
        assert mock_copy2.call_count == 2  # Two files copied

        # Verify tracking data was updated
        assert "User" in generator.tracking_data
        assert "Order" in generator.tracking_data

        # Verify cleanup
        mock_rmtree.assert_called_once_with(temp_dir)


def test_generate_with_progress_no_custom_location(generator, tmp_path):
    """Test code generation with no custom location specified."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    output_dir = tmp_path / "generated"
    temp_dir = "temp_generated"
    model_dir = os.path.join(
        temp_dir, "src/main/java", generator.config.java_package_base.replace(".", "/"), generator.config.model_package
    )

    # Create test spec data without custom location
    spec_data = {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                },
            },
        },
    }

    progress = MagicMock()
    task_id = 1

    with (
        patch("subprocess.run") as mock_run,
        patch("os.makedirs") as mock_makedirs,
        patch("os.listdir") as mock_listdir,
        patch("shutil.copy2") as mock_copy2,
        patch("shutil.rmtree") as mock_rmtree,
        patch.object(generator, "_parse_spec", return_value=spec_data),
    ):
        # Setup mocks
        mock_listdir.return_value = ["User.java"]

        # Run the generator
        generator.generate_with_progress(str(spec_file), str(output_dir), progress, task_id)

        # Verify default directory was created
        default_dir = os.path.join(output_dir, generator.config.model_package)
        mock_makedirs.assert_any_call(default_dir, exist_ok=True)

        # Verify file was copied to default location
        source_path = os.path.join(model_dir, "User.java")
        target_path = os.path.join(default_dir, "User.java")
        mock_copy2.assert_any_call(source_path, target_path)

        # Verify tracking data was updated
        assert "User" in generator.tracking_data
        assert generator.tracking_data["User"] == target_path

        # Verify subprocess was called
        mock_run.assert_called_once()

        # Verify cleanup was performed
        mock_rmtree.assert_called_once_with(temp_dir)
