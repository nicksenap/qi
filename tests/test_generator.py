"""Tests for OpenAPI code generator."""

import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml

from qi.config import Config
from qi.file_processor import FileProcessor, ProcessConfig
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


@pytest.fixture
def file_processor():
    """Create a file processor instance."""
    return FileProcessor(organization="qi", artifact_id="service")


def test_load_tracking_empty_file(generator, tmp_path):
    """Test loading tracking data from empty file."""
    qi_dir = tmp_path / ".qi"
    os.makedirs(qi_dir)
    tracking_file = qi_dir / "tracking.yaml"
    with open(tracking_file, "w") as f:
        f.write("")  # Empty file

    generator.config.tracking_file = str(tracking_file)
    loaded_data = generator._load_tracking()
    assert loaded_data == {}


def test_load_tracking(generator, tmp_path):
    """Test loading tracking data."""
    qi_dir = tmp_path / ".qi"
    os.makedirs(qi_dir)
    tracking_file = qi_dir / "tracking.yaml"
    tracking_data = {
        "models": {
            "User": {
                "file_path": "path/to/User.java",
                "package": "com.qi.service.model",
                "custom_dir": None,
                "java_class_name": "User"
            }
        }
    }
    with open(tracking_file, "w") as f:
        yaml.dump(tracking_data, f)

    generator.config.tracking_file = str(tracking_file)
    loaded_data = generator._load_tracking()
    assert loaded_data == tracking_data["models"]


def test_save_tracking(generator, tmp_path):
    """Test saving tracking data."""
    qi_dir = tmp_path / ".qi"
    os.makedirs(qi_dir)
    tracking_file = qi_dir / "tracking.yaml"
    generator.config.tracking_file = str(tracking_file)
    generator.tracking_data = {
        "User": {
            "file_path": "path/to/User.java",
            "package": "com.qi.service.model",
            "custom_dir": None,
            "java_class_name": "User"
        }
    }

    generator._save_tracking()
    assert tracking_file.exists()

    with open(tracking_file) as f:
        loaded_data = yaml.safe_load(f)
    assert loaded_data == {
        "models": generator.tracking_data
    }


def test_parse_spec(generator):
    """Test parsing OpenAPI specification."""
    spec_file = FIXTURES_DIR / "test_spec.yaml"
    spec_data = generator._parse_spec(str(spec_file))
    assert "openapi" in spec_data
    assert "paths" in spec_data
    assert "components" in spec_data


def test_get_custom_location(file_processor):
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

    location = file_processor._get_custom_location("User", spec_data)
    assert location == "domain/user/model"

    # Test non-existent schema
    location = file_processor._get_custom_location("NonExistent", spec_data)
    assert location is None


def test_update_package_and_imports(file_processor):
    """Test updating package declarations and imports."""
    content = (
        "package com.qi.service.model;\n\n"
        "import com.qi.service.api.UserApi;\n"
        "import com.qi.service.model.User;\n"
        "import com.qi.service.model.Order;\n"
        "import java.util.List;\n"
        "public class Order {\n"
        "    private User user;\n"
        "}\n"
    )
    custom_dir = "model/dto"

    updated_content = file_processor._update_package_and_imports(content, custom_dir)
    assert "package com.qi.service.model.dto;" in updated_content
    assert "import com.qi.service.model.dto.User;" in updated_content
    assert "import com.qi.service.api.UserApi;" in updated_content
    assert "import java.util.List;" in updated_content


def test_update_package_no_extra_dots(file_processor):
    """Test that package declarations don't contain extra dots."""
    content = "package com.qi.service.model;\n\n" "public class Test {}\n"

    # Test with various custom directory formats that might cause extra dots
    test_cases = [
        ("", "package com.qi.service.model;"),  # Default case, no custom directory
        (None, "package com.qi.service.model;"),  # None case
        ("dto", "package com.qi.service.model.dto;"),
        ("model/dto", "package com.qi.service.model.dto;"),
        ("model/dto/", "package com.qi.service.model.dto;"),
        ("/dto", "package com.qi.service.model.dto;"),
        ("dto/", "package com.qi.service.model.dto;"),
        ("dto//sub", "package com.qi.service.model.dto.sub;"),
        ("model//dto", "package com.qi.service.model.dto;"),
    ]

    for custom_dir, expected_package in test_cases:
        updated_content = file_processor._update_package_and_imports(content, custom_dir)
        assert expected_package in updated_content
        assert "package com.qi.service.model..;" not in updated_content
        assert ".." not in updated_content
        assert "package com.qi.service.model.;" not in updated_content  # No trailing dot


@pytest.mark.integration
def test_process_java_files(file_processor, tmp_path):
    """Test processing Java files with custom locations."""
    # Create test spec data with custom location
    spec_data = {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "x-qi-dir": "dto",
                },
                "Order": {
                    "type": "object",
                },
            },
        },
    }

    # Create mock file content
    mock_file_content = "package com.qi.service.model;\n\n" "public class User {\n" "    private String name;\n" "}\n"

    # Setup directories
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    os.makedirs(source_dir)

    # Create mock files in source directory
    (source_dir / "User.java").write_text(mock_file_content)
    (source_dir / "Order.java").write_text(mock_file_content)

    progress = MagicMock()
    task_id = 1

    # Process the files
    file_processor.process_java_files(
        ProcessConfig(
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            file_type="model",
            spec_data=spec_data,
            progress=progress,
            task_id=task_id,
        )
    )

    # Verify file creation with full Java package path including src/main/java
    assert (output_dir / "src/main/java/com/qi/service/model/dto/User.java").exists()
    assert (output_dir / "src/main/java/com/qi/service/model/Order.java").exists()

    # Verify tracking data
    assert "User" in file_processor.tracking_data
    assert "Order" in file_processor.tracking_data

    # Verify file contents
    user_content = (output_dir / "src/main/java/com/qi/service/model/dto/User.java").read_text()
    assert "package com.qi.service.model.dto;" in user_content

    order_content = (output_dir / "src/main/java/com/qi/service/model/Order.java").read_text()
    assert "package com.qi.service.model;" in order_content


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
                    "x-qi-dir": "dto",
                },
                "Order": {
                    "type": "object",
                },
            },
        },
    }

    progress = MagicMock()
    task_id = 1

    # Create mock file content
    mock_file_content = "package com.qi.service.model;\n\n" "public class User {\n" "    private String name;\n" "}\n"

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
        patch("builtins.open", mock_open(read_data=mock_file_content)),
    ):
        # Setup mocks
        mock_listdir.side_effect = lambda x: {
            temp_dir: ["src", "pom.xml", "README.md"],
            model_dir: ["User.java", "Order.java"],
            api_dir: ["UserApi.java", "OrderApi.java"],
        }[x]

        # Run the generator
        generator.generate_with_progress(str(spec_file), str(output_dir), progress, task_id)

        # Verify the calls
        mock_makedirs.assert_called()
        mock_listdir.assert_called()
        mock_copy2.assert_called()
        mock_rmtree.assert_called_with(temp_dir)
        mock_run.assert_called_once()
        mock_copytree.assert_called()


@pytest.mark.integration
def test_process_java_files_cleanup_default_location(file_processor, tmp_path):
    """Test that files with custom locations are cleaned up from default location."""
    # Create test spec data with custom location
    spec_data = {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "x-qi-dir": "dto",
                },
            },
        },
    }

    # Create mock file content
    mock_file_content = "package com.qi.service.model;\n\n" "public class User {\n" "    private String name;\n" "}\n"

    # Setup directories
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    os.makedirs(source_dir)

    # First, create a file in the default location
    default_model_dir = output_dir / "src/main/java/com/qi/service/model"
    os.makedirs(default_model_dir)
    default_file_path = default_model_dir / "User.java"
    default_file_path.write_text(mock_file_content)

    # Create the source file
    (source_dir / "User.java").write_text(mock_file_content)

    progress = MagicMock()
    task_id = 1

    # Process the files
    file_processor.process_java_files(
        ProcessConfig(
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            file_type="model",
            spec_data=spec_data,
            progress=progress,
            task_id=task_id,
            verbose=True,
        )
    )

    # Verify file was moved to custom location
    custom_file_path = output_dir / "src/main/java/com/qi/service/model/dto/User.java"
    assert custom_file_path.exists()

    # Verify file was removed from default location
    assert not default_file_path.exists()

    # Verify file contents in custom location
    custom_content = custom_file_path.read_text()
    assert "package com.qi.service.model.dto;" in custom_content


@pytest.mark.integration
def test_update_imports_with_tracking_data(file_processor, tmp_path):
    """Test that imports are correctly updated based on tracking data."""
    # Setup tracking data
    file_processor.tracking_data = {
        "CreateEventMessageRequest": {
            "file_path": "out/src/main/java/com/qi/service/model/dto/CreateEventMessageRequest.java",
            "package": "com.qi.service.model.dto",
            "custom_dir": "dto",
            "java_class_name": "CreateEventMessageRequest",
        },
        "EventMessageResponse": {
            "file_path": "out/src/main/java/com/qi/service/model/dto/EventMessageResponse.java",
            "package": "com.qi.service.model.dto",
            "custom_dir": "dto",
            "java_class_name": "EventMessageResponse",
        },
    }

    # Create a test API file with imports to be updated
    api_content = """
package com.qi.service.api;

import com.qi.service.model.CreateEventMessageRequest;
import com.qi.service.model.EventMessageResponse;
import org.springframework.http.ResponseEntity;

public class TestApi {
    public ResponseEntity<EventMessageResponse> testMethod(CreateEventMessageRequest request) {
        return null;
    }
}
"""

    # Setup directories and files
    api_dir = tmp_path / "src/main/java/com/qi/service/api"
    os.makedirs(api_dir)
    test_file = api_dir / "TestApi.java"
    test_file.write_text(api_content)

    progress = MagicMock()
    task_id = 1

    # Process the files
    file_processor._update_service_imports(
        ProcessConfig(
            source_dir=str(tmp_path),
            output_dir=str(tmp_path),
            file_type="api",
            spec_data={},
            progress=progress,
            task_id=task_id,
            verbose=True,
        )
    )

    # Read the updated file
    updated_content = test_file.read_text()

    # Verify imports were updated correctly
    assert "import com.qi.service.model.dto.CreateEventMessageRequest;" in updated_content
    assert "import com.qi.service.model.dto.EventMessageResponse;" in updated_content
    assert "import org.springframework.http.ResponseEntity;" in updated_content  # Unchanged import
