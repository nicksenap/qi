import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from rich.progress import Progress, TaskID


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


class FileProcessor:
    """Handles file processing operations for Java files."""

    def __init__(self, organization: str, artifact_id: str):
        self.organization = organization
        self.artifact_id = artifact_id
        self.tracking_data = {}
        self.qi_dir = ".qi"
        self.tracking_file = os.path.join(self.qi_dir, "tracking.yaml")
        os.makedirs(self.qi_dir, exist_ok=True)
        self._load_tracking_data()

    def _load_tracking_data(self):
        """Load tracking data from file if it exists."""
        if os.path.exists(self.tracking_file):
            with open(self.tracking_file) as f:
                data = yaml.safe_load(f)
                if data:
                    self.tracking_data = data.get("models", {})

    def _save_tracking_data(self):
        """Save tracking data to file."""
        tracking_info = {
            "version": "1.0",
            "organization": self.organization,
            "artifact_id": self.artifact_id,
            "models": self.tracking_data,
        }
        with open(self.tracking_file, "w") as f:
            yaml.safe_dump(tracking_info, f)

    def _update_tracking_data(self, model_name: str, info: dict[str, Any]):
        """Update tracking data for a model."""
        self.tracking_data[model_name] = {
            "file_path": info.get("file_path"),
            "package": info.get("package"),
            "custom_dir": info.get("custom_dir"),
            "java_class_name": info.get("java_class_name"),
        }
        self._save_tracking_data()

    def _get_custom_location(self, schema_name: str, spec_data: dict[str, Any]) -> str | None:
        """Get custom location for a schema from tracking data or x-qi-dir."""
        # For tests, if we have spec data with x-qi-dir, use that
        schemas = spec_data.get("components", {}).get("schemas", {})

        # Try exact match first
        if schema_name in schemas and "x-qi-dir" in schemas[schema_name]:
            return schemas[schema_name].get("x-qi-dir")

        # Convert PascalCase to camelCase for lookup
        camel_case_name = schema_name[0].lower() + schema_name[1:]
        if camel_case_name in schemas and "x-qi-dir" in schemas[camel_case_name]:
            return schemas[camel_case_name].get("x-qi-dir")

        # Handle special cases where the schema name might be different from the class name
        # For example: "Case" in spec becomes "ModelCase" in generated code
        if schema_name.startswith("Model"):
            base_name = schema_name[5:]  # Remove "Model" prefix
            if base_name in schemas and "x-qi-dir" in schemas[base_name]:
                return schemas[base_name].get("x-qi-dir")
            # Try camelCase
            camel_base = base_name[0].lower() + base_name[1:]
            if camel_base in schemas and "x-qi-dir" in schemas[camel_base]:
                return schemas[camel_base].get("x-qi-dir")

        # Otherwise check tracking data
        if schema_name in self.tracking_data:
            return self.tracking_data[schema_name].get("custom_dir")

        return None

    def _update_imports(self, content: str, old_package: str, new_package: str) -> str:
        """Update imports in the file content to reflect new package structure."""
        # Get the base package without 'model'
        base_package_root = f"com.{self.organization}.{self.artifact_id}"

        # Update imports from any package under the base package
        lines = content.split("\n")
        updated_lines = []

        for line in lines:
            updated_line = line
            # If it's an import statement from our base package
            if line.strip().startswith("import " + base_package_root):
                # If this import is from the old package
                if old_package in line:
                    # Update to use the new package
                    updated_line = line.replace(old_package, new_package)
            updated_lines.append(updated_line)

        return "\n".join(updated_lines)

    def _update_package_and_imports(self, content: str, custom_dir: str) -> str:
        """Update package declaration and imports in Java file content."""
        # Get the base package
        base_package = f"com.{self.organization}.{self.artifact_id}.model"

        # If no custom directory, just return the content as is
        if not custom_dir:
            return content

        # Extract the subdirectory part, removing 'model/' prefix if present
        subpackage = custom_dir.replace("model/", "").replace("/", ".")
        # Remove any leading or trailing dots and ensure no double dots
        subpackage = subpackage.strip(".")
        new_package = f"{base_package}.{subpackage}".replace("..", ".")

        # Replace the package declaration
        content = content.replace(f"package {base_package};", f"package {new_package};")

        # Update imports
        content = self._update_imports(content, base_package, new_package)

        return content

    def _process_custom_dir_file(
        self, source_path: str, file_name: str, custom_dir: str, config: ProcessConfig, model_name: str
    ):
        """Process a file that has a custom directory specified."""
        # Create the full Java package directory structure
        base_path = os.path.join("src", "main", "java", "com", self.organization, self.artifact_id)
        package_path = os.path.join(base_path, "model", custom_dir)
        full_custom_dir = os.path.join(config.output_dir, package_path)
        os.makedirs(full_custom_dir, exist_ok=True)
        target_path = os.path.join(full_custom_dir, file_name)

        # Clean up any existing file in the default location
        default_dir = os.path.join(config.output_dir, base_path, config.file_type)
        default_file_path = os.path.join(default_dir, file_name)
        try:
            os.remove(default_file_path)
            if config.verbose:
                print(f"Cleaned up file from default location: {default_file_path}")
        except FileNotFoundError:
            pass

        # Read and update file content
        with open(source_path) as f:
            content = f.read()

        # Update package and imports
        content = self._update_package_and_imports(content, custom_dir)

        # Write to target location
        with open(target_path, "w") as f:
            f.write(content)

        # Remove the original file if it exists
        try:
            os.remove(source_path)
        except FileNotFoundError:
            pass

        if config.verbose:
            print(f"Moved and updated file: {file_name}")

        # Update tracking with more detailed information
        base_package = f"com.{self.organization}.{self.artifact_id}.model"
        custom_package = custom_dir.replace("/", ".")
        new_package = f"{base_package}.{custom_package}"
        self._update_tracking_data(
            model_name,
            {
                "file_path": target_path,
                "package": new_package,
                "custom_dir": custom_dir,
                "java_class_name": file_name[:-5],  # Remove .java extension
            },
        )

        config.progress.update(config.task_id, description=f"[yellow]Moved and updated file: {file_name}")

    def _process_default_dir_file(self, source_path: str, file_name: str, config: ProcessConfig, model_name: str):
        """Process a file that goes to the default directory."""
        # Create the full Java package directory structure for default location
        base_path = os.path.join("src", "main", "java", "com", self.organization, self.artifact_id)
        package_path = os.path.join(base_path, config.file_type)
        default_dir = os.path.join(config.output_dir, package_path)
        os.makedirs(default_dir, exist_ok=True)
        target_path = os.path.join(default_dir, file_name)

        # Read and write the file
        with open(source_path) as f:
            content = f.read()
        with open(target_path, "w") as f:
            f.write(content)

        # Try to remove the original file
        try:
            os.remove(source_path)
        except FileNotFoundError:
            pass

        if config.verbose:
            print(f"Moved {file_name} to default location: {default_dir}")
        config.progress.update(config.task_id, description=f"[yellow]Moved {file_name} to default location")

        # Update tracking with full info
        base_package = f"com.{self.organization}.{self.artifact_id}.{config.file_type}"
        self._update_tracking_data(
            model_name,
            {
                "file_path": target_path,
                "package": base_package,
                "custom_dir": None,
                "java_class_name": file_name[:-5],  # Remove .java extension
            },
        )

    def _convert_to_pascal_case(self, name: str) -> str:
        """Convert a camelCase string to PascalCase."""
        return name[0].upper() + name[1:]

    def _build_model_packages_map(self, config: ProcessConfig) -> dict[str, str]:
        """Build a map of model class names to their custom packages."""
        model_packages = {}

        # First add packages from tracking data
        for model_info in self.tracking_data.values():
            if "java_class_name" in model_info and "package" in model_info:
                model_packages[model_info["java_class_name"]] = model_info["package"]

        # Then add packages from spec data for models not yet processed
        schemas = config.spec_data.get("components", {}).get("schemas", {})
        for schema_name, schema in schemas.items():
            if custom_dir := schema.get("x-qi-dir"):
                class_name = self._convert_to_pascal_case(schema_name)
                if class_name not in model_packages:
                    base_package = f"com.{self.organization}.{self.artifact_id}.model"
                    custom_package = custom_dir.replace("/", ".")
                    model_packages[class_name] = f"{base_package}.{custom_package}"

        return model_packages

    def _update_file_imports(
        self,
        file_path: str | Path,
        model_packages: dict[str, str],
        config: ProcessConfig,
    ) -> bool:
        """Update imports in a single file. Returns True if file was modified."""
        with open(file_path) as f:
            content = f.read()

        base_package = f"com.{self.organization}.{self.artifact_id}"
        lines = content.split("\n")
        updated_lines = []
        modified = False

        for line in lines:
            updated_line = line
            if line.strip().startswith("import " + base_package):
                # Extract the class name from the import statement
                parts = line.strip().split(".")
                class_name = parts[-1].rstrip(";")

                # Check if we have a custom package for this class
                if class_name in model_packages:
                    # Get the full package path from tracking data
                    target_package = model_packages[class_name]
                    # Create the new import statement with the correct package
                    updated_line = f"import {target_package}.{class_name};"
                    if updated_line != line:
                        modified = True
                        if config.verbose:
                            print(f"Updated import in {Path(file_path).name}:")
                            print(f"  From: {line.strip()}")
                            print(f"  To:   {updated_line.strip()}")
            updated_lines.append(updated_line)

        if modified:
            updated_content = "\n".join(updated_lines)
            with open(file_path, "w") as f:
                f.write(updated_content)
            if config.verbose:
                print(f"Updated imports in: {Path(file_path).name}")
            config.progress.update(config.task_id, description=f"[yellow]Updated imports in {Path(file_path).name}")
            return True
        return False

    def _update_service_imports(self, config: ProcessConfig):
        """Update imports in service layer files to reflect new model package locations."""
        base_path = os.path.join("src", "main", "java", "com", self.organization, self.artifact_id)
        service_dir = os.path.join(config.output_dir, base_path, "service")
        api_dir = os.path.join(config.output_dir, base_path, "api")

        # Build the model packages map once
        model_packages = self._build_model_packages_map(config)

        if config.verbose:
            print("Updating service and API layer imports...")
        config.progress.update(config.task_id, description="[yellow]Updating service and API layer imports...")

        # Process all Java files in the service and api directories and their subdirectories
        for directory in [service_dir, api_dir]:
            if not os.path.exists(directory):
                continue

            if config.verbose:
                print(f"Checking directory: {directory}")

            for root, _, files in os.walk(directory):
                for file_name in files:
                    if not file_name.endswith(".java"):
                        continue
                    file_path = os.path.join(root, file_name)
                    self._update_file_imports(file_path, model_packages, config)

    def process_java_files(self, config: ProcessConfig):
        """Process Java files from a directory."""
        # First process all model files
        for file_name in os.listdir(config.source_dir):
            if not file_name.endswith(".java"):
                continue

            model_name = file_name[:-5]  # Remove .java extension
            custom_dir = self._get_custom_location(model_name, config.spec_data)

            if config.verbose:
                print(f"Processing {config.file_type} file: {file_name}")
            config.progress.update(config.task_id, description=f"[yellow]Processing {model_name}...")

            source_path = os.path.join(config.source_dir, file_name)

            if custom_dir:
                self._process_custom_dir_file(
                    source_path=source_path,
                    file_name=file_name,
                    custom_dir=custom_dir,
                    config=config,
                    model_name=model_name,
                )
            else:
                self._process_default_dir_file(
                    source_path=source_path, file_name=file_name, config=config, model_name=model_name
                )

        # After all models are processed, update service layer imports
        self._update_service_imports(config)
