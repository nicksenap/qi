from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from .config import Config
from .generator import OpenAPIGenerator
from .linter import DEFAULT_RULES, lint_specs
from .rules import load_custom_rules

console = Console()


def create_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def version_callback(value: bool):
    if value:
        rprint("[green]Qi version 0.1.0[/]")
        raise typer.Exit()


app = typer.Typer(
    help="[bold]Qi[/] - Better Workflow for Contract-Based Development",
    rich_markup_mode="rich",
)


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    [bold]Qi[/] enhances contract-based development workflow by providing more intelligent code
    generation from OpenAPI specifications.
    """
    pass


@app.command()
def generate(
    spec_file: Path = typer.Argument(
        ...,
        help="Path to OpenAPI specification file",
        exists=True,
        dir_okay=False,
        file_okay=True,
        resolve_path=True,
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
        exists=True,
        dir_okay=False,
        file_okay=True,
    ),
    output: Path = typer.Option(
        Path("./generated"),
        "--output",
        "-o",
        help="Base output directory",
    ),
):
    """Generate Java code from OpenAPI specification."""
    try:
        with console.status("[bold green]Loading configuration...") as status:
            config_obj = Config.load(str(config)) if config else Config.default()
            generator = OpenAPIGenerator(config_obj)
            status.update("[bold green]Configuration loaded successfully!")

        with create_progress() as progress:
            download_task = progress.add_task("[cyan]Downloading OpenAPI Generator...", total=None)
            generator.download_generator_with_progress(progress, download_task)

            generate_task = progress.add_task("[yellow]Generating code...", total=None)
            generator.generate_with_progress(str(spec_file), str(output), progress, generate_task)

        rprint("[bold green]✓[/] Code generation completed successfully!")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e!s}")
        raise typer.Exit(1) from e


def validate_version(value: str) -> str:
    """Validate the OpenAPI version."""
    if value not in ["2", "3"]:
        raise typer.BadParameter('Version must be either "2" or "3"')
    return value


@app.command()
def convert(
    spec_file: Path = typer.Argument(
        ...,
        help="Path to OpenAPI specification file",
        exists=True,
        dir_okay=False,
        file_okay=True,
        resolve_path=True,
    ),
    target_version: str = typer.Option(
        ...,
        "--to",
        "-t",
        help="Target OpenAPI version (2 or 3)",
        callback=validate_version,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (optional)",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
        exists=True,
        dir_okay=False,
        file_okay=True,
    ),
):
    """Convert OpenAPI specification between versions 2 and 3."""
    try:
        with console.status("[bold green]Loading configuration...") as status:
            config_obj = Config.load(str(config)) if config else Config.default()
            generator = OpenAPIGenerator(config_obj)
            status.update("[bold green]Configuration loaded successfully!")

        with create_progress() as progress:
            convert_task = progress.add_task("[cyan]Converting specification...", total=None)
            output_file = generator.convert_spec_version(
                str(spec_file),
                target_version,
                str(output) if output else None,
                progress,
                convert_task,
            )

        rprint(f"[bold green]✓[/] Specification converted successfully to: {output_file}")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e!s}")
        raise typer.Exit(1) from e


@app.command()
def lint(
    spec_files: list[Path] = typer.Argument(
        ...,
        help="Paths to OpenAPI specification files",
        exists=True,
        dir_okay=False,
        file_okay=True,
        resolve_path=True,
    ),
    rules_file: Path | None = typer.Option(
        None,
        "--rules",
        "-r",
        help="Path to custom rules YAML file",
        exists=True,
        dir_okay=False,
        file_okay=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed validation messages",
    ),
):
    """Lint OpenAPI specification files for validation errors."""
    try:
        # Load custom rules if provided, otherwise use default rules
        custom_rules = load_custom_rules(rules_file) if rules_file else DEFAULT_RULES

        is_valid = lint_specs(spec_files, verbose, custom_rules=custom_rules)
        if is_valid:
            rprint("[bold green]✓[/] All specifications are valid!")
        else:
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e!s}")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
