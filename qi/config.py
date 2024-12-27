from dataclasses import dataclass

import yaml


@dataclass
class Config:
    openapi_generator_version: str
    java_package_base: str
    model_package: str
    api_package: str
    tracking_file: str

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
            tracking_file=data.get("tracking_file", ".qi-tracking.yaml"),
        )

    @classmethod
    def default(cls) -> "Config":
        """Create default configuration."""
        return cls(
            openapi_generator_version="6.6.0",
            java_package_base="com.example",
            model_package="model",
            api_package="api",
            tracking_file=".qi-tracking.yaml",
        )

    def save(self, path: str):
        """Save configuration to YAML file."""
        data = {
            "openapi_generator_version": self.openapi_generator_version,
            "java_package_base": self.java_package_base,
            "model_package": self.model_package,
            "api_package": self.api_package,
            "tracking_file": self.tracking_file,
        }
        with open(path, "w") as f:
            yaml.dump(data, f)
