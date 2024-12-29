import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from qi.config import Config
from qi.file_operations import ProcessConfig
from qi.file_processor import FileProcessor


@pytest.fixture
def config():
    return Config(
        openapi_generator_version="6.6.0",
        java_package_base="com.test-org",
        model_package="model",
        api_package="api",
        tracking_file=".qi/tracking.yaml",
        artifact_id="test-artifact",
        organization="test-org",
        artifact_version="0.0.1",
        use_java8=True,
        use_spring_boot3=True,
        use_tags=True,
        qi_dir=".qi",
    )


@pytest.fixture
def file_processor(config):
    return FileProcessor("test-org", "test-artifact", config)


@pytest.fixture
def process_config():
    progress_mock = MagicMock()
    task_id_mock = MagicMock()
    return ProcessConfig(
        source_dir="temp/source",
        output_dir="temp/output",
        file_type="model",
        spec_data={"components": {"schemas": {"TestModel": {"x-qi-dir": "custom/path"}, "DefaultModel": {}}}},
        progress=progress_mock,
        task_id=task_id_mock,
        verbose=True,
    )


@pytest.fixture
def setup_test_files(tmp_path):
    """Setup test files and directories."""
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    output_dir.mkdir()

    # Create test model files
    test_model = source_dir / "TestModel.java"
    test_model.write_text("""package com.test-org.test-artifact.model;
public class TestModel {}""")

    default_model = source_dir / "DefaultModel.java"
    default_model.write_text("""package com.test-org.test-artifact.model;
public class DefaultModel {}""")

    # Create service file that imports models
    service_dir = output_dir / "src/main/java/com/test-org/test-artifact/service"
    service_dir.mkdir(parents=True)
    service_file = service_dir / "TestService.java"
    service_file.write_text("""package com.test-org.test-artifact.service;

import com.test-org.test-artifact.model.TestModel;
import com.test-org.test-artifact.model.DefaultModel;

public class TestService {
    private TestModel testModel;
    private DefaultModel defaultModel;
}""")

    return source_dir, output_dir


def test_process_java_files(file_processor, process_config, setup_test_files):
    """Test processing Java files with both custom and default directories."""
    source_dir, output_dir = setup_test_files
    process_config.source_dir = str(source_dir)
    process_config.output_dir = str(output_dir)

    file_processor.process_java_files(process_config)

    # Check custom directory file
    custom_path = output_dir / "src/main/java/com/test-org/test-artifact/model/custom/path/TestModel.java"
    assert custom_path.exists()
    content = custom_path.read_text()
    assert "package com.test-org.test-artifact.model.custom.path;" in content

    # Check default directory file
    default_path = output_dir / "src/main/java/com/test-org/test-artifact/model/DefaultModel.java"
    assert default_path.exists()
    content = default_path.read_text()
    assert "package com.test-org.test-artifact.model;" in content

    # Check service file imports were updated
    service_path = output_dir / "src/main/java/com/test-org/test-artifact/service/TestService.java"
    content = service_path.read_text()
    assert "import com.test-org.test-artifact.model.custom.path.TestModel;" in content
    assert "import com.test-org.test-artifact.model.DefaultModel;" in content


def test_build_model_packages_map(file_processor, process_config):
    """Test building model packages map from tracking data and spec data."""
    # Add some tracking data
    file_processor.tracking_manager.tracking_data = {
        "TrackedModel": {"package": "com.test-org.test-artifact.model.tracked", "java_class_name": "TrackedModel"}
    }

    packages_map = file_processor._build_model_packages_map(process_config)

    assert "TestModel" in packages_map
    assert packages_map["TestModel"] == "com.test-org.test-artifact.model.custom.path"
    assert "TrackedModel" in packages_map
    assert packages_map["TrackedModel"] == "com.test-org.test-artifact.model.tracked"


def test_update_file_imports(file_processor, tmp_path):
    """Test updating imports in a file."""
    # Create a test file
    test_file = tmp_path / "TestFile.java"
    test_file.write_text("""package com.test-org.test-artifact.service;

import com.test-org.test-artifact.model.TestModel;
import com.test-org.test-artifact.model.OtherModel;

public class TestFile {
    private TestModel test;
    private OtherModel other;
}""")

    # Create a mock config
    progress_mock = MagicMock()
    task_id_mock = MagicMock()
    config = ProcessConfig(
        source_dir="",
        output_dir="",
        file_type="",
        spec_data={},
        progress=progress_mock,
        task_id=task_id_mock,
        verbose=True,
    )

    # Create model packages map
    model_packages = {
        "TestModel": "com.test-org.test-artifact.model.custom.path",
        "OtherModel": "com.test-org.test-artifact.model.other.path",
    }

    # Update imports
    file_processor._update_file_imports(test_file, model_packages, config)

    # Check the content
    content = test_file.read_text()
    assert "import com.test-org.test-artifact.model.custom.path.TestModel;" in content
    assert "import com.test-org.test-artifact.model.other.path.OtherModel;" in content


def test_is_fresh_generation(file_processor, tmp_path):
    """Test detection of fresh generation."""
    # Empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert file_processor._is_fresh_generation(str(empty_dir)) is True

    # Non-existent directory
    non_existent = tmp_path / "non_existent"
    assert file_processor._is_fresh_generation(str(non_existent)) is True

    # Existing project
    project_dir = tmp_path / "project"
    java_path = project_dir / "src/main/java/com/test-org/test-artifact"
    java_path.mkdir(parents=True)
    assert file_processor._is_fresh_generation(str(project_dir)) is False


def test_has_model_changed(file_processor, tmp_path):
    """Test detection of model changes."""
    # Create a test file
    model_file = tmp_path / "TestModel.java"
    model_file.write_text("""
package com.test-org.test-artifact.model;
public class TestModel {
    private String name;
}""")

    # Test with existing model in spec
    spec_data = {
        "components": {"schemas": {"TestModel": {"type": "object", "properties": {"name": {"type": "string"}}}}}
    }
    assert file_processor._has_model_changed("TestModel", str(model_file), spec_data) is True

    # Test with non-existent file
    non_existent = tmp_path / "NonExistent.java"
    assert file_processor._has_model_changed("NonExistent", str(non_existent), spec_data) is True

    # Test with model removed from spec
    assert file_processor._has_model_changed("RemovedModel", str(model_file), spec_data) is False


def test_process_java_files_fresh_generation(file_processor, process_config, setup_test_files):
    """Test processing Java files for fresh generation."""
    source_dir, output_dir = setup_test_files
    process_config.source_dir = str(source_dir)
    process_config.output_dir = str(output_dir)

    # Remove any existing files to simulate fresh generation
    shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    file_processor.process_java_files(process_config)

    # Verify all files were generated
    custom_path = output_dir / "src/main/java/com/test-org/test-artifact/model/custom/path/TestModel.java"
    assert custom_path.exists()
    content = custom_path.read_text()
    assert "package com.test-org.test-artifact.model.custom.path;" in content

    default_path = output_dir / "src/main/java/com/test-org/test-artifact/model/DefaultModel.java"
    assert default_path.exists()
    content = default_path.read_text()
    assert "package com.test-org.test-artifact.model;" in content


def test_process_java_files_existing_project(file_processor, process_config, setup_test_files):
    """Test processing Java files for existing project."""
    source_dir, output_dir = setup_test_files
    process_config.source_dir = str(source_dir)
    process_config.output_dir = str(output_dir)

    # Create existing files
    java_path = output_dir / "src/main/java/com/test-org/test-artifact"
    model_dir = java_path / "model"
    model_dir.mkdir(parents=True, exist_ok=True)

    # Create the existing model with original content
    existing_model = model_dir / "ExistingModel.java"
    existing_content = """package com.test-org.test-artifact.model;
public class ExistingModel {
    private String name;
}"""
    existing_model.write_text(existing_content)

    # Create source file with updated content
    source_model = Path(source_dir) / "ExistingModel.java"
    updated_content = """package com.test-org.test-artifact.model;
public class ExistingModel {
    private String name;
    private String newField;
}"""
    source_model.write_text(updated_content)

    # Add existing model to spec with changes
    process_config.spec_data["components"]["schemas"]["ExistingModel"] = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "newField": {"type": "string"},  # Added field
        },
    }

    file_processor.process_java_files(process_config)

    # Verify existing model was updated (because it changed in spec)
    assert existing_model.exists()
    final_content = existing_model.read_text()
    assert "newField" in final_content  # Check for the new field

    # Verify new models were added
    custom_path = output_dir / "src/main/java/com/test-org/test-artifact/model/custom/path/TestModel.java"
    assert custom_path.exists()
    content = custom_path.read_text()
    assert "package com.test-org.test-artifact.model.custom.path;" in content
