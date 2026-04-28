"""Interactive scorecard filler — walk through each model and enter scores."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import IntPrompt, Prompt

console = Console()

DIMENSIONS = [
    ("skeleton", "Skeleton Placement"),
    ("skinning", "Skinning Deformation"),
    ("extremity", "Extremity Handling (tail/ears/paws)"),
    ("joints", "Joint Bend Direction"),
]


@click.command()
@click.argument("scorecard_path", type=click.Path(exists=True))
def main(scorecard_path: str):
    """Interactively fill scores for each model in the scorecard."""
    path = Path(scorecard_path)
    cards = json.loads(path.read_text())

    console.print(f"\n[bold]Scoring {len(cards)} models[/bold]")
    console.print("Rate each dimension 1-5 (1=terrible, 5=perfect)\n")

    for i, card in enumerate(cards):
        console.rule(f"[{i + 1}/{len(cards)}] {card['file']}")
        console.print(f"  Open this file in a 3D viewer to inspect.\n")

        for key, label in DIMENSIONS:
            score = IntPrompt.ask(f"  {label}", default=card.get(key, 0))
            card[key] = max(1, min(5, score))

        card["notes"] = Prompt.ask("  Notes (optional)", default=card.get("notes", ""))
        console.print()

    path.write_text(json.dumps(cards, indent=2, ensure_ascii=False))
    console.print(f"[green]Scorecard saved:[/green] {path}")


if __name__ == "__main__":
    main()
