import os
import shutil
import subprocess
import tempfile
from typing import Any, Literal

import requests
import yaml
from apispec import APISpec
from rich.progress import Progress, TaskID

from .config import Config


class OpenAPIGenerator:
    def __init__(self, config: Config):
        self.config = config
        self.tracking_data = self._load_tracking()

    def _load_tracking(self) -> dict[str, str]:
        """Load tracking data from file."""
        if os.path.exists(self.config.tracking_file):
            with open(self.config.tracking_file) as f:
                return yaml.safe_load(f) or {}
        return {}

    def _save_tracking(self):
        """Save tracking data to file."""
        with open(self.config.tracking_file, "w") as f:
            yaml.dump(self.tracking_data, f)

    def download_generator_with_progress(self, progress: Progress, task_id: TaskID) -> str:
        """Download OpenAPI Generator CLI jar with progress reporting."""
        jar_name = f"openapi-generator-cli-{self.config.openapi_generator_version}.jar"
        if os.path.exists(jar_name):
            progress.update(task_id, description="[green]OpenAPI Generator already downloaded")
            return jar_name

        url = f"https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/{self.config.openapi_generator_version}/openapi-generator-cli-{self.config.openapi_generator_version}.jar"
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get("content-length", 0))

        progress.update(task_id, total=total_size)
        progress.start_task(task_id)

        with open(jar_name, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

        progress.update(task_id, description="[green]Download completed!")
        return jar_name

    def _parse_spec(self, spec_file: str) -> dict[str, Any]:
        """Parse OpenAPI specification to extract x-qi-dir information."""
        with open(spec_file) as f:
            return yaml.safe_load(f)

    def _get_custom_location(self, schema_name: str, spec_data: dict[str, Any]) -> str | None:
        """Get custom location for a schema from x-qi-dir."""
        schemas = spec_data.get("components", {}).get("schemas", {})
        if schema_name in schemas:
            return schemas[schema_name].get("x-qi-dir")
        return None

    def generate_with_progress(self, spec_file: str, output_dir: str, progress: Progress, task_id: TaskID):
        """Generate code and manage file locations with progress reporting."""
        # Parse specification
        progress.update(task_id, description="[yellow]Parsing OpenAPI specification...")
        spec_data = self._parse_spec(spec_file)

        # Create temporary directory for generation
        temp_dir = "temp_generated"
        os.makedirs(temp_dir, exist_ok=True)

        # Generate code
        progress.update(task_id, description="[yellow]Running OpenAPI Generator...")
        jar_path = f"openapi-generator-cli-{self.config.openapi_generator_version}.jar"
        cmd = [
            "java",
            "-jar",
            jar_path,
            "generate",
            "-i",
            spec_file,
            "-g",
            "spring",
            "-o",
            temp_dir,
            "--api-package",
            f"{self.config.java_package_base}.{self.config.api_package}",
            "--model-package",
            f"{self.config.java_package_base}.{self.config.model_package}",
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # Process generated files
        progress.update(task_id, description="[yellow]Processing generated files...")
        model_dir = os.path.join(
            temp_dir, "src/main/java", self.config.java_package_base.replace(".", "/"), self.config.model_package
        )

        for file_name in os.listdir(model_dir):
            if not file_name.endswith(".java"):
                continue

            model_name = file_name[:-5]  # Remove .java extension
            custom_dir = self._get_custom_location(model_name, spec_data)
            progress.update(task_id, description=f"[yellow]Processing {model_name}...")

            if custom_dir:
                # Create custom directory if it doesn't exist
                full_custom_dir = os.path.join(output_dir, custom_dir)
                os.makedirs(full_custom_dir, exist_ok=True)

                source_path = os.path.join(model_dir, file_name)
                target_path = os.path.join(full_custom_dir, file_name)

                if os.path.exists(target_path):
                    progress.update(task_id, description=f"[yellow]Updating existing file: {file_name}")
                    # TODO: Implement smart merge for existing files
                    shutil.copy2(source_path, target_path)
                else:
                    progress.update(task_id, description=f"[yellow]Creating new file: {file_name}")
                    shutil.copy2(source_path, target_path)

                # Update tracking
                self.tracking_data[model_name] = target_path
            else:
                # Move to default location
                default_dir = os.path.join(output_dir, self.config.model_package)
                os.makedirs(default_dir, exist_ok=True)

                source_path = os.path.join(model_dir, file_name)
                target_path = os.path.join(default_dir, file_name)

                progress.update(task_id, description=f"[yellow]Moving {file_name} to default location")
                shutil.copy2(source_path, target_path)
                self.tracking_data[model_name] = target_path

        # Save tracking data
        progress.update(task_id, description="[yellow]Saving tracking data...")
        self._save_tracking()

        # Cleanup
        progress.update(task_id, description="[yellow]Cleaning up...")
        shutil.rmtree(temp_dir)

        progress.update(task_id, description="[green]Generation completed!")

    def _convert_schemas(self, spec_data: dict, target_version: str, spec: APISpec) -> None:
        """Convert schemas between OpenAPI versions."""
        if target_version == "3" and "definitions" in spec_data:
            for name, schema in spec_data["definitions"].items():
                spec.components.schema(name, schema)
        elif target_version == "2" and "components" in spec_data and "schemas" in spec_data["components"]:
            for name, schema in spec_data["components"]["schemas"].items():
                spec.components.schema(name, schema)

    def convert_spec_version(
        self,
        spec_file: str,
        target_version: Literal["2", "3"],
        output_file: str | None = None,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> str:
        """Convert OpenAPI specification between versions 2 and 3."""
        if progress and task_id:
            progress.update(task_id, description=f"[yellow]Converting specification to version {target_version}...")

        with open(spec_file) as f:
            spec_data = yaml.safe_load(f)

        current_version = "2" if spec_data.get("swagger") == "2.0" else "3"
        if current_version == target_version:
            if progress and task_id:
                progress.update(task_id, description="[green]Specification already in target version")
            if output_file:
                shutil.copy2(spec_file, output_file)
                return output_file
            return spec_file

        openapi_version = "2.0" if target_version == "2" else "3.0.0"
        spec = APISpec(
            title=spec_data.get("info", {}).get("title", "Converted API"),
            version=spec_data.get("info", {}).get("version", "1.0.0"),
            openapi_version=openapi_version,
        )

        if "paths" in spec_data:
            for path, path_item in spec_data["paths"].items():
                spec.path(path=path, operations=path_item)

        self._convert_schemas(spec_data, target_version, spec)
        converted_dict = spec.to_dict()

        if target_version == "2" and "components" in converted_dict and "schemas" in converted_dict["components"]:
            converted_dict["definitions"] = converted_dict["components"]["schemas"]
            del converted_dict["components"]

        output_file = output_file or tempfile.mktemp(suffix=".yaml")
        with open(output_file, "w") as f:
            yaml.dump(converted_dict, f)

        if progress and task_id:
            progress.update(task_id, description="[green]Conversion completed!")

        return output_file
