"""Evaluation suite: batch score pipeline outputs on 4 dimensions.

Dimensions:
1. Skeleton placement — are bones in correct positions?
2. Skinning deformation — does the mesh deform naturally?
3. Extremity handling — tail, ears, paws correct or broken?
4. Joint bend direction — knees bend the right way?

For Week 1 PoC, scoring is manual (human review). This script generates
a scorecard template and aggregates results.
"""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

DIMENSIONS = [
    ("skeleton", "Skeleton Placement (1-5)"),
    ("skinning", "Skinning Deformation (1-5)"),
    ("extremity", "Extremity Handling (1-5)"),
    ("joints", "Joint Bend Direction (1-5)"),
]


def generate_scorecard(results_dir: Path) -> Path:
    """Create a JSON scorecard template for all GLB files in a directory."""
    glb_files = sorted(results_dir.glob("animated_*.glb"))
    if not glb_files:
        glb_files = sorted(results_dir.glob("*.glb"))

    cards = []
    for f in glb_files:
        cards.append({
            "file": f.name,
            "skeleton": 0,
            "skinning": 0,
            "extremity": 0,
            "joints": 0,
            "notes": "",
        })

    out_path = results_dir / "scorecard.json"
    out_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False))
    console.print(f"[green]Scorecard template:[/green] {out_path} ({len(cards)} items)")
    console.print("Fill in scores 1-5 for each dimension, then run --summarize")
    return out_path


def summarize(scorecard_path: Path):
    """Read filled scorecard and print summary statistics."""
    cards = json.loads(scorecard_path.read_text())

    table = Table(title="Evaluation Summary")
    table.add_column("File", style="cyan", max_width=30)
    for _, label in DIMENSIONS:
        table.add_column(label, justify="center")
    table.add_column("Avg", justify="center", style="bold")
    table.add_column("Notes", max_width=40)

    totals = {d[0]: 0 for d in DIMENSIONS}
    count = 0

    for card in cards:
        scores = [card.get(d[0], 0) for d in DIMENSIONS]
        if any(s > 0 for s in scores):
            count += 1
            for d, s in zip(DIMENSIONS, scores):
                totals[d[0]] += s

        avg = sum(scores) / len(scores) if any(s > 0 for s in scores) else 0
        style = "green" if avg >= 4 else "yellow" if avg >= 3 else "red"
        table.add_row(
            card["file"],
            *[str(s) if s > 0 else "-" for s in scores],
            f"[{style}]{avg:.1f}[/{style}]",
            card.get("notes", ""),
        )

    console.print(table)

    if count > 0:
        console.print("\n[bold]Averages across scored items:[/bold]")
        for key, label in DIMENSIONS:
            avg = totals[key] / count
            console.print(f"  {label}: {avg:.2f}")


@click.command()
@click.option("--generate", type=click.Path(exists=True), help="Generate scorecard for directory")
@click.option("--summarize-file", "summarize_path", type=click.Path(exists=True), help="Summarize filled scorecard")
def main(generate: str | None, summarize_path: str | None):
    if generate:
        generate_scorecard(Path(generate))
    elif summarize_path:
        summarize(Path(summarize_path))
    else:
        console.print("[red]Use --generate <dir> or --summarize-file <scorecard.json>[/red]")


if __name__ == "__main__":
    main()
