import os
from dataclasses import dataclass
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


class TrackingManager:
    """Manages tracking data for generated files."""

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

    def save_tracking_data(self):
        """Save tracking data to file."""
        tracking_info = {
            "version": "1.0",
            "organization": self.organization,
            "artifact_id": self.artifact_id,
            "models": self.tracking_data,
        }
        with open(self.tracking_file, "w") as f:
            yaml.safe_dump(tracking_info, f)

    def update_tracking(self, model_name: str, info: dict[str, Any]):
        """Update tracking data for a model."""
        self.tracking_data[model_name] = {
            "file_path": info.get("file_path"),
            "package": info.get("package"),
            "custom_dir": info.get("custom_dir"),
            "java_class_name": info.get("java_class_name"),
        }
        self.save_tracking_data()

    def get_custom_location(self, schema_name: str, spec_data: dict[str, Any]) -> str | None:
        """Get custom location for a schema from tracking data or x-qi-dir."""
        schemas = spec_data.get("components", {}).get("schemas", {})

        # Try exact match first
        if schema_name in schemas and "x-qi-dir" in schemas[schema_name]:
            return schemas[schema_name].get("x-qi-dir")

        # Convert PascalCase to camelCase for lookup
        camel_case_name = schema_name[0].lower() + schema_name[1:]
        if camel_case_name in schemas and "x-qi-dir" in schemas[camel_case_name]:
            return schemas[camel_case_name].get("x-qi-dir")

        # Handle special cases where the schema name might be different from the class name
        if schema_name.startswith("Model"):
            base_name = schema_name[5:]  # Remove "Model" prefix
            if base_name in schemas and "x-qi-dir" in schemas[base_name]:
                return schemas[base_name].get("x-qi-dir")
            camel_base = base_name[0].lower() + base_name[1:]
            if camel_base in schemas and "x-qi-dir" in schemas[camel_base]:
                return schemas[camel_base].get("x-qi-dir")

        # Check tracking data
        if schema_name in self.tracking_data:
            return self.tracking_data[schema_name].get("custom_dir")

        return None


class PackageUpdater:
    """Handles package and import updates in Java files."""

    def __init__(self, organization: str, artifact_id: str):
        self.organization = organization
        self.artifact_id = artifact_id
        self.base_package_root = f"com.{organization}.{artifact_id}"

    def update_imports(self, content: str, old_package: str, new_package: str) -> str:
        """Update imports in the file content to reflect new package structure."""
        lines = content.split("\n")
        updated_lines = []

        for line in lines:
            updated_line = line
            if line.strip().startswith("import " + self.base_package_root):
                if old_package in line:
                    updated_line = line.replace(old_package, new_package)
            updated_lines.append(updated_line)

        return "\n".join(updated_lines)

    def update_package_and_imports(self, content: str, custom_dir: str) -> str:
        """Update package declaration and imports in Java file content."""
        if not custom_dir:
            return content

        # Split content into lines for processing
        lines = content.split("\n")
        updated_lines = []

        for line in lines:
            updated_line = line
            if line.strip().startswith("package "):
                # Extract the original package name without the semicolon
                original_package = line.strip()[8:-1]  # Remove 'package ' and ';'

                # Convert custom directory path to package format and remove any leading/trailing slashes
                package_suffix = custom_dir.strip("/").replace("//", "/").replace("/", ".")

                # Split the original package into components
                package_parts = original_package.split(".")

                # Find the base package (everything up to and including the first occurrence of 'model')
                model_index = -1
                for i, part in enumerate(package_parts):
                    if part == "model":
                        model_index = i
                        break

                if model_index != -1:
                    # Keep everything up to and including the first 'model'
                    base_package = ".".join(package_parts[:model_index + 1])

                    # Remove any 'model' prefix from the custom directory if it exists
                    suffix_parts = package_suffix.split(".")
                    if suffix_parts[0] == "model":
                        suffix_parts = suffix_parts[1:]
                    clean_suffix = ".".join(suffix_parts)

                    # Create the new package name
                    new_package = f"{base_package}.{clean_suffix}" if clean_suffix else base_package
                else:
                    # If 'model' is not found, use the original package as base
                    new_package = f"{original_package}.{package_suffix}"

                updated_line = f"package {new_package};"
            elif line.strip().startswith("import "):
                # Update imports to reflect the new package structure
                import_line = line.strip()
                if import_line.startswith("import " + self.base_package_root):
                    for old_part in ["model.model.", ".."]:
                        import_line = import_line.replace(old_part, ".")
                updated_line = import_line
            updated_lines.append(updated_line)

        return "\n".join(updated_lines)


class FileMover:
    """Handles moving and organizing generated files."""

    def __init__(self, organization: str, artifact_id: str, tracking_manager: TrackingManager):
        self.organization = organization
        self.artifact_id = artifact_id
        self.tracking_manager = tracking_manager
        self.package_updater = PackageUpdater(organization, artifact_id)

    def move_to_custom_dir(
        self, source_path: str, file_name: str, custom_dir: str, config: ProcessConfig, model_name: str
    ):
        """Move and process a file to its custom directory."""
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

        # Update content and write to new location
        with open(source_path) as f:
            content = f.read()

        # First update the package declaration using PackageUpdater
        content = self.package_updater.update_package_and_imports(content, custom_dir)

        # Then ensure the package name is correct by direct replacement
        base_package = f"com.{self.organization}.{self.artifact_id}.model"
        custom_package = custom_dir.strip("/").replace("/", ".")
        new_package = f"{base_package}.{custom_package}"
        content = content.replace(f"package {base_package};", f"package {new_package};")

        with open(target_path, "w") as f:
            f.write(content)

        try:
            os.remove(source_path)
        except FileNotFoundError:
            pass

        if config.verbose:
            print(f"Moved and updated file: {file_name}")

        # Update tracking
        self.tracking_manager.update_tracking(
            model_name,
            {
                "file_path": target_path,
                "package": new_package,
                "custom_dir": custom_dir,
                "java_class_name": file_name[:-5],
            },
        )

        config.progress.update(config.task_id, description=f"[yellow]Moved and updated file: {file_name}")
        return target_path

    def move_to_default_dir(self, source_path: str, file_name: str, config: ProcessConfig, model_name: str):
        """Move and process a file to the default directory."""
        base_path = os.path.join("src", "main", "java", "com", self.organization, self.artifact_id)
        package_path = os.path.join(base_path, config.file_type)
        default_dir = os.path.join(config.output_dir, package_path)
        os.makedirs(default_dir, exist_ok=True)
        target_path = os.path.join(default_dir, file_name)

        with open(source_path) as f:
            content = f.read()
        with open(target_path, "w") as f:
            f.write(content)

        try:
            os.remove(source_path)
        except FileNotFoundError:
            pass

        if config.verbose:
            print(f"Moved {file_name} to default location: {default_dir}")
        config.progress.update(config.task_id, description=f"[yellow]Moved {file_name} to default location")

        base_package = f"com.{self.organization}.{self.artifact_id}.{config.file_type}"
        self.tracking_manager.update_tracking(
            model_name,
            {
                "file_path": target_path,
                "package": base_package,
                "custom_dir": None,
                "java_class_name": file_name[:-5],
            },
        )
        return target_path
