import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qi.cli import app

runner = CliRunner()


@pytest.fixture
def spec_file(tmp_path):
    # Copy the test spec to a temporary location
    src = Path("tests/fixtures/test_spec.yaml")
    dst = tmp_path / "test_spec.yaml"
    shutil.copy2(src, dst)
    return dst


def test_version():
    """Test version command."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "QI version" in result.stdout


def test_help():
    """Test help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "QI" in result.stdout
    assert "generate" in result.stdout


def test_generate_help():
    """Test generate command help."""
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    assert "Generate Java code" in result.stdout


@pytest.mark.integration
def test_generate_command(spec_file, tmp_path):
    """Test generate command with minimal arguments."""
    output_dir = tmp_path / "generated"
    result = runner.invoke(app, ["generate", str(spec_file), "-o", str(output_dir)])

    assert result.exit_code == 0
    assert "completed successfully" in result.stdout

    # Verify files were generated
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


@pytest.mark.integration
def test_generate_with_config(spec_file, tmp_path):
    """Test generate command with config file."""
    # Create test config
    config_data = """
    openapi_generator_version: "6.6.0"
    java_package_base: "com.test"
    model_package: "testmodel"
    api_package: "testapi"
    tracking_file: ".test-tracking.yaml"
    """
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_data)

    output_dir = tmp_path / "generated"
    result = runner.invoke(app, ["generate", str(spec_file), "-c", str(config_file), "-o", str(output_dir)])

    assert result.exit_code == 0
    assert "completed successfully" in result.stdout

    # Verify files were generated with correct package
    user_path = output_dir / "domain/user/model/User.java"
    assert user_path.exists()

    # Verify the content has the correct package and types
    with open(user_path) as f:
        content = f.read()
        assert "package com.test.testmodel;" in content
        assert "public class User" in content
        assert "private UUID id;" in content
        assert '@Schema(name = "id", description = "The user\'s unique identifier"' in content


def test_generate_invalid_spec():
    """Test generate command with non-existent spec file."""
    result = runner.invoke(app, ["generate", "nonexistent.yaml"])
    assert result.exit_code != 0
    assert "Error" in result.stdout


def test_generate_invalid_config(spec_file):
    """Test generate command with non-existent config file."""
    result = runner.invoke(app, ["generate", str(spec_file), "-c", "nonexistent.yaml"])
    assert result.exit_code != 0
    assert "Error" in result.stdout
