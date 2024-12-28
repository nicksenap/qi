import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

import requests
import yaml
from rich.progress import Progress, TaskID

from .config import Config


@dataclass
class ProcessConfig:
    """Configuration for processing Java files."""

    source_dir: str
    output_dir: str
    file_type: str
    spec_data: dict
    progress: Progress
    task_id: TaskID
    verbose: bool = False


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

    def generate_with_progress(
        self,
        spec_file: str,
        output_dir: str,
        progress: Progress,
        task_id: TaskID,
        verbose: bool = False,
    ):
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
        ]

        # Add additional properties
        additional_properties = {
            "java8": str(self.config.use_java8).lower(),
            "artifactId": self.config.artifact_id,
            "groupId": f"com.{self.config.organization}.{self.config.artifact_id}",
            "artifactVersion": self.config.artifact_version,
            "apiPackage": f"com.{self.config.organization}.{self.config.artifact_id}.api",
            "modelPackage": f"com.{self.config.organization}.{self.config.artifact_id}.model",
            "useTags": str(self.config.use_tags).lower(),
            "useSpringBoot3": str(self.config.use_spring_boot3).lower(),
        }

        for key, value in additional_properties.items():
            cmd.append(f"--additional-properties={key}={value}")

        if verbose:
            progress.update(task_id, description="[yellow]Running OpenAPI Generator with verbose output...")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("\nOpenAPI Generator Output:")
            print(result.stdout)
            if result.stderr:
                print("\nOpenAPI Generator Errors:")
                print(result.stderr)
        else:
            subprocess.run(cmd, check=True, capture_output=True)

        # First, copy all generated files to output directory
        progress.update(task_id, description="[yellow]Copying generated files...")
        os.makedirs(output_dir, exist_ok=True)
        for item in os.listdir(temp_dir):
            source = os.path.join(temp_dir, item)
            destination = os.path.join(output_dir, item)
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)

        # Then process model and api files with special handling
        progress.update(task_id, description="[yellow]Processing generated files...")
        base_java_path = os.path.join(
            temp_dir, "src/main/java", "com", self.config.organization, self.config.artifact_id
        )

        # Process model files
        model_dir = os.path.join(base_java_path, "model")
        if os.path.exists(model_dir):
            if verbose:
                print("\nProcessing model files...")
            self._process_java_files(
                ProcessConfig(
                    source_dir=model_dir,
                    output_dir=output_dir,
                    file_type="model",
                    spec_data=spec_data,
                    progress=progress,
                    task_id=task_id,
                    verbose=verbose,
                )
            )

        # Process API files
        api_dir = os.path.join(base_java_path, "api")
        if os.path.exists(api_dir):
            if verbose:
                print("\nProcessing API files...")
            self._process_java_files(
                ProcessConfig(
                    source_dir=api_dir,
                    output_dir=output_dir,
                    file_type="api",
                    spec_data=spec_data,
                    progress=progress,
                    task_id=task_id,
                    verbose=verbose,
                )
            )

        # Save tracking data
        progress.update(task_id, description="[yellow]Saving tracking data...")
        self._save_tracking()

        # Cleanup
        progress.update(task_id, description="[yellow]Cleaning up...")
        shutil.rmtree(temp_dir)

        progress.update(task_id, description="[green]Generation completed!")

    def _process_java_files(self, config: ProcessConfig):
        """Process Java files from a directory."""
        for file_name in os.listdir(config.source_dir):
            if not file_name.endswith(".java"):
                continue

            model_name = file_name[:-5]  # Remove .java extension
            custom_dir = self._get_custom_location(model_name, config.spec_data)
            if config.verbose:
                print(f"Processing {config.file_type} file: {file_name}")
            config.progress.update(config.task_id, description=f"[yellow]Processing {model_name}...")

            if custom_dir:
                # Create custom directory if it doesn't exist
                full_custom_dir = os.path.join(config.output_dir, custom_dir)
                os.makedirs(full_custom_dir, exist_ok=True)

                source_path = os.path.join(config.source_dir, file_name)
                target_path = os.path.join(full_custom_dir, file_name)

                if os.path.exists(target_path):
                    if config.verbose:
                        print(f"Updating existing file: {file_name}")
                    config.progress.update(config.task_id, description=f"[yellow]Updating existing file: {file_name}")
                    # TODO: Implement smart merge for existing files
                    shutil.copy2(source_path, target_path)
                else:
                    if config.verbose:
                        print(f"Creating new file: {file_name}")
                    config.progress.update(config.task_id, description=f"[yellow]Creating new file: {file_name}")
                    shutil.copy2(source_path, target_path)

                # Update tracking
                self.tracking_data[model_name] = target_path
            else:
                # Move to default location
                default_dir = os.path.join(config.output_dir, config.file_type)
                os.makedirs(default_dir, exist_ok=True)

                source_path = os.path.join(config.source_dir, file_name)
                target_path = os.path.join(default_dir, file_name)

                if config.verbose:
                    print(f"Moving {file_name} to default location: {default_dir}")
                config.progress.update(config.task_id, description=f"[yellow]Moving {file_name} to default location")
                shutil.copy2(source_path, target_path)
                self.tracking_data[model_name] = target_path
