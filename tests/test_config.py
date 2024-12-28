import pytest
import yaml

from qi.config import Config


@pytest.fixture
def config_file(tmp_path):
    config_data = {
        "openapi_generator_version": "6.6.0",
        "java_package_base": "com.test",
        "model_package": "testmodel",
        "api_package": "testapi",
        "tracking_file": ".test-tracking.yaml",
    }
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)
    return config_path


def test_config_load(config_file):
    """Test loading configuration from file."""
    config = Config.load(str(config_file))
    assert config.openapi_generator_version == "6.6.0"
    assert config.java_package_base == "com.test"
    assert config.model_package == "testmodel"
    assert config.api_package == "testapi"
    assert config.tracking_file == ".test-tracking.yaml"


def test_config_default():
    """Test default configuration."""
    config = Config.default()
    assert config.openapi_generator_version == "6.6.0"
    assert config.java_package_base == "com.example"
    assert config.model_package == "model"
    assert config.api_package == "api"
    assert config.tracking_file == ".qi-tracking.yaml"


def test_config_save(tmp_path):
    """Test saving configuration to file."""
    config = Config(
        openapi_generator_version="6.6.0",
        java_package_base="com.test",
        model_package="testmodel",
        api_package="testapi",
        tracking_file=".test-tracking.yaml",
        artifact_id="test-service",
        organization="test",
        artifact_version="1.0.0",
        use_java8=True,
        use_spring_boot3=True,
        use_tags=True,
    )

    save_path = tmp_path / "saved_config.yaml"
    config.save(str(save_path))

    # Load and verify
    loaded_config = Config.load(str(save_path))
    assert loaded_config.openapi_generator_version == config.openapi_generator_version
    assert loaded_config.java_package_base == config.java_package_base
    assert loaded_config.model_package == config.model_package
    assert loaded_config.api_package == config.api_package
    assert loaded_config.tracking_file == config.tracking_file
