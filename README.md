# Qi - Better Workflow for Contract-Based Development

[![Test](https://github.com/nicksenap/qi/actions/workflows/test.yml/badge.svg)](https://github.com/nicksenap/qi/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/nicksenap/qi/graph/badge.svg)](https://codecov.io/gh/nicksenap/qi)

Qi (契, means contract in Chinese) is a tool that enhances contract-based development workflow by providing more intelligent code generation from OpenAPI specifications. Currently supporting Java Spring Boot, with planned support for FastAPI and other frameworks.

## Features

- Automatically downloads and manages OpenAPI Generator CLI
- Supports custom directory mapping via `x-qi-dir` extension
- Tracks generated files for smart updates
- Currently supports Java Spring Boot projects (FastAPI and other frameworks coming soon)

## Installation

First, make sure you have `uv` installed:
```bash
pip install uv
```

Then install QI:
```bash
uv pip install .
```

## Usage

### Basic Usage

```bash
qi generate path/to/spec.yaml -o ./target
```

### With Configuration File

Create a configuration file `qi-config.yaml`:

```yaml
openapi_generator_version: "6.6.0"
java_package_base: "com.example"
model_package: "model"
api_package: "api"
tracking_file: ".qi-tracking.yaml"
```

Then run:

```bash
qi generate path/to/spec.yaml -c qi-config.yaml -o ./target
```

### OpenAPI Specification Example

```yaml
components:
  schemas:
    User:
      x-qi-dir: "domain/user/model"  # Custom directory for User model
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
```

## Development

### Setup

```bash
# Install development dependencies
make install.dev

# Run tests
make test          # All tests
make test.unit     # Unit tests only
make test.integration  # Integration tests only

# Code quality
make lint          # Check code style
make fix           # Auto-fix code style issues
make check         # Run all quality checks
```

## Requirements

- Python 3.10+
- Java Runtime Environment (JRE) for OpenAPI Generator
- uv for dependency management
