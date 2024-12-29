import os
from pathlib import Path

from .config import Config
from .file_operations import FileMover, ProcessConfig, TrackingManager


class FileProcessor:
    """Handles file processing operations for Java files."""

    def __init__(self, organization: str, artifact_id: str, config: Config):
        self.organization = organization
        self.artifact_id = artifact_id
        self.config = config
        self.java_package_base = f"com.{organization}.{artifact_id}"
        self.tracking_manager = TrackingManager(organization, artifact_id)
        self.file_mover = FileMover(organization, artifact_id, self.tracking_manager)

    def _get_target_path(self, model_name: str, config: ProcessConfig) -> str:
        """Get the target path for a model."""
        custom_dir = self.tracking_manager.get_custom_location(model_name, config.spec_data)
        base_path = os.path.join(config.output_dir, "src/main/java", self.java_package_base.replace(".", "/"))
        if custom_dir:
            return os.path.join(base_path, custom_dir, f"{model_name}.java")
        return os.path.join(base_path, "model", f"{model_name}.java")

    def _is_fresh_generation(self, output_dir: str) -> bool:
        """Check if this is a fresh generation (empty or non-existent output dir)."""
        if not os.path.exists(output_dir):
            return True

        java_path = os.path.join(
            output_dir,
            "src",
            "main",
            "java",
            "com",
            self.organization,
            self.artifact_id,
        )
        return not os.path.exists(java_path)

    def determine_update_strategy(self, output_dir: str, spec_data: dict) -> tuple[bool, str]:
        """Determine whether to do a fresh generation or incremental update.

        Args:
            output_dir: The output directory path
            spec_data: The parsed OpenAPI spec data

        Returns:
            tuple[bool, str]: (is_fresh, reason)
                is_fresh: True for fresh generation, False for incremental
                reason: Explanation of why this strategy was chosen
        """
        # Check if it's a fresh generation case
        if self._is_fresh_generation(output_dir):
            return True, "Output directory is empty or doesn't contain Java files"

        # Check if we have tracking data
        if not self.tracking_manager.tracking_data:
            return True, "No tracking data found from previous generation"

        # Check if there are significant schema changes
        if "components" not in spec_data or "schemas" not in spec_data["components"]:
            return True, "No schema definitions found in spec"

        schemas = spec_data["components"]["schemas"]
        tracked_models = set(self.tracking_manager.tracking_data.keys())
        spec_models = set(schemas.keys())

        # If there are new models, we can still do incremental
        new_models = spec_models - tracked_models
        # If models were removed, we can still do incremental
        removed_models = tracked_models - spec_models

        # For now, always do incremental if we have tracking data and valid schemas
        # Later we can add more sophisticated checks
        return False, f"Incremental update (New models: {len(new_models)}, Removed: {len(removed_models)})"

    def _has_model_changed(self, model_name: str, file_path: str, spec_data: dict) -> bool:
        """Check if a model has changed compared to its spec.

        Returns:
            bool: True if the model needs to be updated:
                - If the file doesn't exist
                - If the model exists in both file and spec (for now, until proper comparison is implemented)
            False if the model should be skipped:
                - If the file exists but model is not in the spec (deleted/moved)
                - If there's no schema data
        """
        # If file doesn't exist, it needs to be generated
        if not os.path.exists(file_path):
            return True

        # Check if model exists in spec
        if "components" not in spec_data or "schemas" not in spec_data["components"]:
            return False

        model_spec = spec_data["components"]["schemas"].get(model_name)
        if not model_spec:
            # Model exists in files but not in spec - skip it
            return False

        # For now, always return True if model exists in spec and file exists
        # This ensures we update existing models with any potential changes
        # TODO: Implement proper comparison using tree-sitter
        return True

    def _convert_to_pascal_case(self, name: str) -> str:
        """Convert a camelCase string to PascalCase."""
        return name[0].upper() + name[1:]

    def _build_model_packages_map(self, spec_data: dict | ProcessConfig) -> dict[str, str]:
        """Build a map of model class names to their custom packages."""
        model_packages = {}

        # First add packages from tracking data
        for model_info in self.tracking_manager.tracking_data.values():
            if "java_class_name" in model_info and "package" in model_info:
                model_packages[model_info["java_class_name"]] = model_info["package"]

        # Then add packages from spec data for models not yet processed
        if isinstance(spec_data, ProcessConfig):
            spec_data = spec_data.spec_data

        schemas = spec_data.get("components", {}).get("schemas", {})
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
        model_packages = self._build_model_packages_map(config.spec_data)
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
        """Process Java files from source directory."""
        is_fresh = self._is_fresh_generation(config.output_dir)

        # Process each file in the source directory
        for file_name in os.listdir(config.source_dir):
            if not file_name.endswith(".java"):
                continue

            source_file = os.path.join(config.source_dir, file_name)
            model_name = file_name[:-5]  # Remove .java extension

            # For fresh generation or if model has changed, process the file
            target_path = self._get_target_path(model_name, config)
            if is_fresh or self._has_model_changed(model_name, target_path, config.spec_data):
                if config.file_type == "model":
                    self._process_model_file(source_file, model_name, config)
                else:
                    self._process_api_file(source_file, model_name, config)

        # Update imports in all Java files
        self._update_service_imports(config)

    def _process_model_file(self, source_file: str, model_name: str, config: ProcessConfig) -> str:
        """Process a model file.

        Returns:
            str: The target path where the file was moved to.
        """
        custom_dir = self.tracking_manager.get_custom_location(model_name, config.spec_data)
        file_name = os.path.basename(source_file)

        # Read the source file content
        with open(source_file) as f:
            content = f.read()

        # Update the package name if it's going to a custom directory
        if custom_dir:
            base_package = f"com.{self.organization}.{self.artifact_id}.model"
            custom_package = custom_dir.strip("/").replace("/", ".")
            new_package = f"{base_package}.{custom_package}"
            content = content.replace(f"package {base_package};", f"package {new_package};")

            # Write the updated content back to the source file
            with open(source_file, "w") as f:
                f.write(content)

            target_path = self.file_mover.move_to_custom_dir(source_file, file_name, custom_dir, config, model_name)
        else:
            target_path = self.file_mover.move_to_default_dir(source_file, file_name, config, model_name)
        return target_path

    def _process_api_file(self, source_file: str, api_name: str, config: ProcessConfig) -> str:
        """Process an API file.

        Returns:
            str: The target path where the file was moved to.
        """
        return self.file_mover.move_to_default_dir(source_file, os.path.basename(source_file), config, api_name)
