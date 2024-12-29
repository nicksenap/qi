import pytest

from qi.config import Config
from qi.file_processor import FileProcessor
from qi.generator import OpenAPIGenerator


@pytest.fixture
def config():
    return Config(
        openapi_generator_version="6.6.0",
        java_package_base="com.test",
        model_package="model",
        api_package="api",
        tracking_file=".qi/tracking.yaml",
        artifact_id="service",
        organization="test",
        artifact_version="0.0.1",
        use_java8=True,
        use_spring_boot3=True,
        use_tags=True,
        qi_dir=".qi",
    )


@pytest.fixture
def incremental_file_processor(config):
    return FileProcessor(config.organization, config.artifact_id, config)


@pytest.fixture
def incremental_generator(config):
    return OpenAPIGenerator(config)


def test_detect_fresh_generation(incremental_file_processor, tmp_path):
    """Test detection of fresh vs existing project."""
    # Empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert incremental_file_processor._is_fresh_generation(str(empty_dir)) is True

    # Create a Java project structure
    project_dir = tmp_path / "project"
    java_path = project_dir / "src/main/java/com/test/service"
    java_path.mkdir(parents=True)
    assert incremental_file_processor._is_fresh_generation(str(project_dir)) is False
