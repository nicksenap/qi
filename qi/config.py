from dataclasses import dataclass

import yaml


@dataclass
class Config:
    openapi_generator_version: str
    java_package_base: str
    model_package: str
    api_package: str
    tracking_file: str
    artifact_id: str
    organization: str
    artifact_version: str
    use_java8: bool
    use_spring_boot3: bool
    use_tags: bool
    qi_dir: str = ".qi"

    @classmethod
    def load(cls, config_path: str) -> "Config":
        """Load configuration from YAML file."""
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return cls(
            openapi_generator_version=data.get("openapi_generator_version", "6.6.0"),
            java_package_base=data["java_package_base"],
            model_package=data.get("model_package", "model"),
            api_package=data.get("api_package", "api"),
            tracking_file=data.get("tracking_file", ".qi/tracking.yaml"),
            artifact_id=data.get("artifact_id", "service"),
            organization=data.get("organization", "qi"),
            artifact_version=data.get("artifact_version", "0.0.1"),
            use_java8=data.get("use_java8", True),
            use_spring_boot3=data.get("use_spring_boot3", True),
            use_tags=data.get("use_tags", True),
            qi_dir=data.get("qi_dir", ".qi"),
        )

    @classmethod
    def default(cls) -> "Config":
        """Create default configuration."""
        return cls(
            openapi_generator_version="6.6.0",
            java_package_base="com.example",
            model_package="model",
            api_package="api",
            tracking_file=".qi/tracking.yaml",
            artifact_id="service",
            organization="qi",
            artifact_version="0.0.1",
            use_java8=True,
            use_spring_boot3=True,
            use_tags=True,
            qi_dir=".qi",
        )

    def save(self, path: str):
        """Save configuration to YAML file."""
        data = {
            "openapi_generator_version": self.openapi_generator_version,
            "java_package_base": self.java_package_base,
            "model_package": self.model_package,
            "api_package": self.api_package,
            "tracking_file": self.tracking_file,
            "artifact_id": self.artifact_id,
            "organization": self.organization,
            "artifact_version": self.artifact_version,
            "use_java8": self.use_java8,
            "use_spring_boot3": self.use_spring_boot3,
            "use_tags": self.use_tags,
            "qi_dir": self.qi_dir,
        }
        with open(path, "w") as f:
            yaml.dump(data, f)
