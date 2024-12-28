import os
from pathlib import Path

from .file_operations import FileMover, ProcessConfig, TrackingManager


class FileProcessor:
    """Handles file processing operations for Java files."""

    def __init__(self, organization: str, artifact_id: str):
        self.organization = organization
        self.artifact_id = artifact_id
        self.tracking_manager = TrackingManager(organization, artifact_id)
        self.file_mover = FileMover(organization, artifact_id, self.tracking_manager)

    def _convert_to_pascal_case(self, name: str) -> str:
        """Convert a camelCase string to PascalCase."""
        return name[0].upper() + name[1:]

    def _build_model_packages_map(self, config: ProcessConfig) -> dict[str, str]:
        """Build a map of model class names to their custom packages."""
        model_packages = {}

        # First add packages from tracking data
        for model_info in self.tracking_manager.tracking_data.values():
            if "java_class_name" in model_info and "package" in model_info:
                model_packages[model_info["java_class_name"]] = model_info["package"]

        # Then add packages from spec data for models not yet processed
        schemas = config.spec_data.get("components", {}).get("schemas", {})
        for schema_name, schema in schemas.items():
            if custom_dir := schema.get("x-qi-dir"):
                class_name = self._convert_to_pascal_case(schema_name)
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
        """Update imports in a file based on model packages."""
        with open(file_path) as f:
            content = f.read()

        updated = False
        lines = content.split("\n")
        updated_lines = []

        base_package = f"com.{self.organization}.{self.artifact_id}"
        for line in lines:
            updated_line = line
            if line.strip().startswith("import " + base_package):
                for model_name, package in model_packages.items():
                    if f".model.{model_name}" in line:
                        updated_line = line.replace(f"{base_package}.model", package)
                        updated = True
                        break
            updated_lines.append(updated_line)

        if updated:
            with open(file_path, "w") as f:
                f.write("\n".join(updated_lines))

        return updated

    def _update_service_imports(self, config: ProcessConfig):
        """Update imports in service files."""
        model_packages = self._build_model_packages_map(config)
        if not model_packages:
            return

        base_path = os.path.join(
            config.output_dir,
            "src",
            "main",
            "java",
            "com",
            self.organization,
            self.artifact_id,
        )

        for root, _, files in os.walk(base_path):
            for file in files:
                if not file.endswith(".java"):
                    continue
                file_path = os.path.join(root, file)
                if self._update_file_imports(file_path, model_packages, config):
                    if config.verbose:
                        print(f"Updated imports in {file}")
                    config.progress.update(
                        config.task_id,
                        description=f"[yellow]Updated imports in {file}",
                    )

    def process_java_files(self, config: ProcessConfig):
        """Process generated Java files."""
        for file_name in os.listdir(config.source_dir):
            if not file_name.endswith(".java"):
                continue

            source_path = os.path.join(config.source_dir, file_name)
            model_name = file_name[:-5]  # Remove .java extension

            custom_dir = self.tracking_manager.get_custom_location(model_name, config.spec_data)

            if custom_dir:
                self.file_mover.move_to_custom_dir(source_path, file_name, custom_dir, config, model_name)
            else:
                self.file_mover.move_to_default_dir(source_path, file_name, config, model_name)

        self._update_service_imports(config)
