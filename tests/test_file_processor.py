from unittest.mock import MagicMock

import pytest

from qi.file_operations import ProcessConfig
from qi.file_processor import FileProcessor


@pytest.fixture
def file_processor():
    return FileProcessor("test-org", "test-artifact")


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
