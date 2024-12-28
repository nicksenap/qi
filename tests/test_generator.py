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
def mock_progress():
    """Create a mock progress object."""
    return MagicMock()


@pytest.fixture
def mock_task_id():
    """Create a mock task ID."""
    return 1


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
    java_path = os.path.join("src/main/java", "com")
    base_path = os.path.join(temp_dir, java_path, generator.config.organization, generator.config.artifact_id)
    model_dir = os.path.join(base_path, "model")
    api_dir = os.path.join(base_path, "api")

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
        patch("shutil.copytree") as mock_copytree,
        patch("shutil.rmtree") as mock_rmtree,
        patch.object(generator, "_parse_spec", return_value=spec_data),
        patch("os.path.exists", return_value=True),
        patch("os.path.isdir", lambda x: x.endswith("src")),
    ):
        # Setup mocks
        mock_listdir.side_effect = lambda x: {
            temp_dir: ["src", "pom.xml", "README.md"],
            model_dir: ["User.java", "Order.java"],
            api_dir: ["UserApi.java", "OrderApi.java"],
        }[x]

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
        mock_makedirs.assert_any_call(os.path.join(output_dir, "model"), exist_ok=True)
        mock_makedirs.assert_any_call(os.path.join(output_dir, "api"), exist_ok=True)

        # Verify file operations
        expected_listdir_calls = [
            ((temp_dir,),),
            ((model_dir,),),
            ((api_dir,),),
        ]
        assert mock_listdir.call_args_list == expected_listdir_calls

        # Verify copy operations
        # Should have copied pom.xml and README.md with copy2
        assert mock_copy2.call_count >= 2  # Non-directory files from temp_dir
        # Should have copied src directory with copytree
        mock_copytree.assert_called_once_with(
            os.path.join(temp_dir, "src"), os.path.join(output_dir, "src"), dirs_exist_ok=True
        )

        # Verify tracking data was updated
        assert "User" in generator.tracking_data
        assert "Order" in generator.tracking_data
        assert "UserApi" in generator.tracking_data
        assert "OrderApi" in generator.tracking_data

        # Verify cleanup
        mock_rmtree.assert_called_once_with(temp_dir)


def test_generate_with_progress_no_custom_location(generator, tmp_path):
    """Test code generation with no custom location specified."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    output_dir = tmp_path / "generated"
    temp_dir = "temp_generated"
    java_path = os.path.join("src/main/java", "com")
    base_path = os.path.join(temp_dir, java_path, generator.config.organization, generator.config.artifact_id)
    model_dir = os.path.join(base_path, "model")
    api_dir = os.path.join(base_path, "api")

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
        patch("shutil.copytree") as mock_copytree,
        patch("shutil.rmtree") as mock_rmtree,
        patch.object(generator, "_parse_spec", return_value=spec_data),
        patch("os.path.exists", return_value=True),
        patch("os.path.isdir", lambda x: x.endswith("src")),
    ):
        # Setup mocks
        mock_listdir.side_effect = lambda x: {
            temp_dir: ["src", "pom.xml", "README.md"],
            model_dir: ["User.java"],
            api_dir: ["UserApi.java"],
        }[x]

        # Run the generator
        generator.generate_with_progress(str(spec_file), str(output_dir), progress, task_id)

        # Verify directory creation
        mock_makedirs.assert_any_call(os.path.join(output_dir, "model"), exist_ok=True)
        mock_makedirs.assert_any_call(os.path.join(output_dir, "api"), exist_ok=True)

        # Verify file operations
        expected_listdir_calls = [
            ((temp_dir,),),
            ((model_dir,),),
            ((api_dir,),),
        ]
        assert mock_listdir.call_args_list == expected_listdir_calls

        # Verify copy operations
        # Should have copied pom.xml and README.md with copy2
        assert mock_copy2.call_count >= 2  # Non-directory files from temp_dir
        # Should have copied src directory with copytree
        mock_copytree.assert_called_once_with(
            os.path.join(temp_dir, "src"), os.path.join(output_dir, "src"), dirs_exist_ok=True
        )

        # Verify tracking data was updated
        assert "User" in generator.tracking_data
        assert "UserApi" in generator.tracking_data

        # Verify subprocess was called
        mock_run.assert_called_once()

        # Verify cleanup was performed
        mock_rmtree.assert_called_once_with(temp_dir)


def test_generate_with_custom_organization_and_artifact(tmp_path):
    """Test generation with custom organization and artifact_id."""
    # Create a minimal OpenAPI spec
    spec_file = tmp_path / "test_spec.yaml"
    spec_content = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {},
        "components": {
            "schemas": {
                "TestModel": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                }
            }
        },
    }
    with open(spec_file, "w") as f:
        yaml.dump(spec_content, f)

    # Create config with custom organization and artifact_id
    config = Config(
        openapi_generator_version="6.6.0",
        java_package_base="com.example",
        model_package="model",
        api_package="api",
        tracking_file=".qi-tracking.yaml",
        artifact_id="custom-service",
        organization="custom-org",
        artifact_version="1.0.0",
        use_java8=True,
        use_spring_boot3=True,
        use_tags=True,
    )

    generator = OpenAPIGenerator(config)
    output_dir = tmp_path / "output"
    temp_dir = "temp_generated"
    java_path = os.path.join("src/main/java", "com")
    base_path = os.path.join(temp_dir, java_path, config.organization, config.artifact_id)
    model_dir = os.path.join(base_path, "model")
    api_dir = os.path.join(base_path, "api")

    progress = MagicMock()
    task_id = 1

    with (
        patch("subprocess.run") as mock_run,
        patch("os.makedirs") as mock_makedirs,
        patch("os.listdir") as mock_listdir,
        patch("shutil.copy2") as mock_copy2,
        patch("shutil.copytree") as mock_copytree,
        patch("shutil.rmtree") as mock_rmtree,
        patch.object(generator, "_parse_spec", return_value=spec_content),
        patch("os.path.exists", return_value=True),
        patch("os.path.isdir", lambda x: x.endswith("src")),
    ):
        # Setup mocks
        mock_listdir.side_effect = lambda x: {
            temp_dir: ["src", "pom.xml", "README.md"],
            model_dir: ["TestModel.java"],
            api_dir: ["TestModelApi.java"],
        }[x]

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

        # Verify correct additional properties
        additional_props = [arg for arg in cmd_args if arg.startswith("--additional-properties=")]
        assert f"--additional-properties=artifactId={config.artifact_id}" in additional_props
        assert f"--additional-properties=groupId=com.{config.organization}.{config.artifact_id}" in additional_props

        # Verify directory creation
        mock_makedirs.assert_any_call(temp_dir, exist_ok=True)
        mock_makedirs.assert_any_call(os.path.join(output_dir, "model"), exist_ok=True)
        mock_makedirs.assert_any_call(os.path.join(output_dir, "api"), exist_ok=True)

        # Verify file operations
        expected_listdir_calls = [
            ((temp_dir,),),
            ((model_dir,),),
            ((api_dir,),),
        ]
        assert mock_listdir.call_args_list == expected_listdir_calls

        # Verify copy operations
        # Should have copied pom.xml and README.md with copy2
        assert mock_copy2.call_count >= 2  # Non-directory files from temp_dir
        # Should have copied src directory with copytree
        mock_copytree.assert_called_once_with(
            os.path.join(temp_dir, "src"), os.path.join(output_dir, "src"), dirs_exist_ok=True
        )

        # Verify tracking data
        assert "TestModel" in generator.tracking_data
        assert "TestModelApi" in generator.tracking_data

        # Verify cleanup was performed
        mock_rmtree.assert_called_once_with(temp_dir)
