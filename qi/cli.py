import typer
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint
from typing import Optional
from .generator import OpenAPIGenerator
from .config import Config

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
        rprint("[green]QI version 0.1.0[/]")
        raise typer.Exit()

app = typer.Typer(
    help="[bold]QI[/] - Smart OpenAPI Generator proxy for Java Spring Boot projects",
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
    [bold]QI[/] helps you manage OpenAPI generated code in your Java Spring Boot project.
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
    config: Optional[Path] = typer.Option(
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
        console.print(f"[bold red]Error:[/] {str(e)}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app() 