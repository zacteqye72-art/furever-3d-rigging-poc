"""Stage 4: Animation orchestrator.

For Week 1 PoC this is a thin wrapper — Tripo retarget already bakes
the animation in Stage 3A. This module exists to:
1. Provide a clean interface for future Blender procedural animations
2. Log animation metadata for evaluation
"""

from pathlib import Path

from rich.console import Console

console = Console()


def run(animated_file: Path, output_dir: Path | None = None) -> Path:
    """Stage 4 passthrough for API-generated animations.

    In Week 2 this will branch to Blender procedural scripts
    (breathing, blink, tail wag) when the input is a rigged-only file.
    """
    console.rule("[bold]Stage 4: Animation")

    if not animated_file or not animated_file.exists():
        console.print("[red]No animated file provided[/red]")
        raise FileNotFoundError(f"Missing: {animated_file}")

    console.print(f"  animated file: {animated_file.name}")
    console.print(f"  size: {animated_file.stat().st_size / 1024:.0f} KB")
    console.print("[green]Animation ready (Tripo retarget preset)[/green]")

    return animated_file
