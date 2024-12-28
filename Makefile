.PHONY: install install.dev test test.unit test.integration test.cov lint format clean build check all

# Python environment variables
PYTHON := python3
VENV := .venv
BIN := $(VENV)/bin

# Install development dependencies (use this for development)
install.dev:
	uv venv
	uv pip install -e ".[test]"
	uv pip install ruff
	@echo "\nDevelopment installation complete. Changes to source code will be reflected immediately.\n"

# Install production dependencies (use this for production/deployment only)
install:
	uv venv
	uv pip install .

# Run all tests
test: clean
	$(BIN)/pytest

# Run only unit tests
test.unit: clean
	$(BIN)/pytest -m "not integration"

# Run only integration tests
test.integration: clean
	$(BIN)/pytest -m "integration"

# Run tests with coverage
test.cov: clean
	$(BIN)/pytest --cov=qi --cov-report=html --cov-report=term-missing

# Run linting
lint:
	$(BIN)/ruff check qi tests

# Format code
format:
	$(BIN)/ruff format qi tests

# Auto-fix linting issues
fix:
	$(BIN)/ruff check --fix qi tests
	$(BIN)/ruff format qi tests

# Clean build artifacts and cache
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf temp_generated/
	rm -rf openapi-generator-cli-*.jar
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Super clean, remove the virtual environment, for local development
super-clean: clean
	rm -rf $(VENV)/

# Build package
build: clean
	uv pip install build
	$(PYTHON) -m build

# Run all quality checks
check: clean lint test

# Default target
all: clean install.dev lint test 