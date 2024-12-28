import os
import shutil
from unittest.mock import MagicMock

import pytest

from qi.file_operations import FileMover, ProcessConfig, TrackingManager


@pytest.fixture
def tracking_manager():
    # Clean up any existing tracking file before creating manager
    qi_dir = ".qi"
    tracking_file = os.path.join(qi_dir, "tracking.yaml")
    if os.path.exists(tracking_file):
        os.remove(tracking_file)
    if os.path.exists(qi_dir):
        shutil.rmtree(qi_dir)

    manager = TrackingManager("test-org", "test-artifact")
    yield manager
    # Cleanup after test
    if os.path.exists(manager.tracking_file):
        os.remove(manager.tracking_file)
    if os.path.exists(manager.qi_dir):
        shutil.rmtree(manager.qi_dir)


@pytest.fixture
def file_mover(tracking_manager):
    return FileMover("test-org", "test-artifact", tracking_manager)


@pytest.fixture
def process_config():
    progress_mock = MagicMock()
    task_id_mock = MagicMock()
    return ProcessConfig(
        source_dir="temp/source",
        output_dir="temp/output",
        file_type="model",
        spec_data={"components": {"schemas": {"TestModel": {"x-qi-dir": "custom/path"}}}},
        progress=progress_mock,
        task_id=task_id_mock,
        verbose=True,
    )


def test_tracking_manager_initialization(tracking_manager):
    """Test TrackingManager initialization creates necessary directories."""
    assert os.path.exists(tracking_manager.qi_dir)
    assert tracking_manager.organization == "test-org"
    assert tracking_manager.artifact_id == "test-artifact"
    assert tracking_manager.tracking_data == {}


def test_tracking_manager_save_and_load(tracking_manager):
    """Test saving and loading tracking data."""
    test_data = {
        "test_model": {
            "file_path": "path/to/file",
            "package": "com.test.package",
            "custom_dir": "custom/dir",
            "java_class_name": "TestModel",
        }
    }
    tracking_manager.tracking_data = test_data
    tracking_manager.save_tracking_data()

    # Create new instance to test loading
    new_manager = TrackingManager("test-org", "test-artifact")
    assert new_manager.tracking_data == test_data


def test_tracking_manager_get_custom_location(tracking_manager):
    """Test getting custom location from different sources."""
    spec_data = {
        "components": {
            "schemas": {"TestModel": {"x-qi-dir": "custom/path"}, "testCamelCase": {"x-qi-dir": "camel/path"}}
        }
    }

    # Test exact match
    assert tracking_manager.get_custom_location("TestModel", spec_data) == "custom/path"

    # Test camelCase to PascalCase conversion
    assert tracking_manager.get_custom_location("TestCamelCase", spec_data) == "camel/path"

    # Test Model prefix handling
    tracking_manager.tracking_data = {"SimpleModel": {"custom_dir": "tracked/path"}}
    assert tracking_manager.get_custom_location("SimpleModel", spec_data) == "tracked/path"


def test_package_updater_imports(file_mover):
    """Test updating package and imports in file content."""
    content = """package com.test-org.test-artifact.model;

import com.test-org.test-artifact.model.OtherModel;
import com.test-org.test-artifact.model.subpackage.SubModel;

public class TestModel {
    private OtherModel other;
    private SubModel sub;
}"""

    updated = file_mover.package_updater.update_package_and_imports(content, "custom/path")
    assert "package com.test-org.test-artifact.model.custom.path;" in updated
    assert "import com.test-org.test-artifact.model.custom.path.OtherModel;" not in updated
    assert "import com.test-org.test-artifact.model.subpackage.SubModel;" in updated


@pytest.fixture
def setup_test_files(tmp_path):
    """Setup test files and directories."""
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    output_dir.mkdir()

    test_file = source_dir / "TestModel.java"
    test_file.write_text("""package com.test-org.test-artifact.model;
public class TestModel {}""")

    return source_dir, output_dir


def test_file_mover_custom_dir(file_mover, process_config, setup_test_files):
    """Test moving file to custom directory."""
    source_dir, output_dir = setup_test_files
    process_config.source_dir = str(source_dir)
    process_config.output_dir = str(output_dir)

    source_path = source_dir / "TestModel.java"
    custom_dir = "custom/path"

    file_mover.move_to_custom_dir(str(source_path), "TestModel.java", custom_dir, process_config, "TestModel")

    expected_path = output_dir / "src/main/java/com/test-org/test-artifact/model/custom/path/TestModel.java"
    assert expected_path.exists()
    content = expected_path.read_text()
    assert "package com.test-org.test-artifact.model.custom.path;" in content


def test_file_mover_default_dir(file_mover, process_config, setup_test_files):
    """Test moving file to default directory."""
    source_dir, output_dir = setup_test_files
    process_config.source_dir = str(source_dir)
    process_config.output_dir = str(output_dir)

    source_path = source_dir / "TestModel.java"

    file_mover.move_to_default_dir(str(source_path), "TestModel.java", process_config, "TestModel")

    expected_path = output_dir / "src/main/java/com/test-org/test-artifact/model/TestModel.java"
    assert expected_path.exists()
    content = expected_path.read_text()
    assert "package com.test-org.test-artifact.model;" in content
