"""OpenAPI specification version conversion functionality."""

from pathlib import Path
from typing import Any, Literal

import yaml
from apispec import APISpec
from rich.progress import Progress, TaskID


class OpenAPIConverter:
    """Converter for OpenAPI specifications between versions 2 and 3."""

    @staticmethod
    def _convert_schemas(spec_data: dict[str, Any], target_version: str, spec: APISpec) -> None:
        """Convert schemas between OpenAPI versions."""
        if target_version == "3" and "definitions" in spec_data:
            # Convert OpenAPI 2.0 definitions to OpenAPI 3.0 components/schemas
            for name, schema in spec_data["definitions"].items():
                spec.components.schema(name, schema)
        elif target_version == "2" and "components" in spec_data and "schemas" in spec_data["components"]:
            # Convert OpenAPI 3.0 components/schemas to OpenAPI 2.0 definitions
            for name, schema in spec_data["components"]["schemas"].items():
                spec.components.schema(name, schema)

    def convert_spec(
        self,
        spec_file: Path | str,
        target_version: Literal["2", "3"],
        output_file: Path | str | None = None,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> Path:
        """Convert OpenAPI specification between versions 2 and 3.

        Args:
            spec_file: Path to the input specification file
            target_version: Target OpenAPI version ("2" or "3")
            output_file: Optional path for the output file
            progress: Optional progress bar
            task_id: Optional task ID for progress reporting

        Returns:
            Path to the converted specification file
        """
        if progress and task_id:
            progress.update(task_id, description=f"[yellow]Converting specification to version {target_version}...")

        spec_file = Path(spec_file)
        with open(spec_file) as f:
            spec_data = yaml.safe_load(f)

        # Determine current version
        current_version = "2" if spec_data.get("swagger") == "2.0" else "3"
        if current_version == target_version:
            if progress and task_id:
                progress.update(task_id, description="[green]Specification already in target version")
            if output_file:
                output_file = Path(output_file)
                output_file.write_bytes(spec_file.read_bytes())
                return output_file
            return spec_file

        # Create APISpec instance for conversion
        openapi_version = "2.0" if target_version == "2" else "3.0.0"
        spec = APISpec(
            title=spec_data.get("info", {}).get("title", "Converted API"),
            version=spec_data.get("info", {}).get("version", "1.0.0"),
            openapi_version=openapi_version,
        )

        # Convert paths
        if "paths" in spec_data:
            for path, path_item in spec_data["paths"].items():
                spec.path(path=path, operations=path_item)

        # Convert schemas
        self._convert_schemas(spec_data, target_version, spec)
        converted_dict = spec.to_dict()

        # Handle OpenAPI 2.0 specific conversion
        if target_version == "2" and "components" in converted_dict and "schemas" in converted_dict["components"]:
            converted_dict["definitions"] = converted_dict["components"]["schemas"]
            del converted_dict["components"]

        # Write output
        output_file = Path(output_file) if output_file else spec_file.with_suffix(".converted.yaml")
        output_file.write_text(yaml.dump(converted_dict))

        if progress and task_id:
            progress.update(task_id, description="[green]Conversion completed!")

        return output_file

    def convert_spec_version(
        self,
        spec_file: str,
        target_version: Literal["2", "3"],
        output_file: str | None = None,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> str:
        """Convert OpenAPI specification between versions 2 and 3."""
        result = self.convert_spec(spec_file, target_version, output_file, progress, task_id)
        return str(result)
