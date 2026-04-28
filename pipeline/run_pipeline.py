"""End-to-end CLI runner: pet photo → animated 3D model.

Usage:
    python -m pipeline.run_pipeline --image <url_or_path> [--output-dir <dir>]
    python -m pipeline.run_pipeline --batch <dir_of_images> [--output-dir <dir>]
"""

import json
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from config import config
from pipeline import stage1_image_to_3d, stage2_mesh_prep, stage3a_rig_tripo, stage4_animate

console = Console()


def run_single(image_url: str, output_dir: Path) -> dict:
    """Run full pipeline on a single image. Returns result dict."""
    result = {
        "image_url": image_url,
        "timings": {},
        "costs": {},
        "files": {},
        "errors": [],
    }

    # Stage 1: Seed3D-2.0
    t0 = time.time()
    try:
        seed3d_file = stage1_image_to_3d.run(image_url, output_dir)
        result["timings"]["stage1_seed3d"] = round(time.time() - t0, 1)
        result["files"]["seed3d"] = str(seed3d_file)
    except Exception as e:
        result["errors"].append(f"stage1: {e}")
        console.print(f"[red]Stage 1 failed: {e}[/red]")
        return result

    # Stage 2: Quad remesh via fal.ai Tripo
    t0 = time.time()
    try:
        remeshed_file = stage2_mesh_prep.run(image_url, output_dir)
        result["timings"]["stage2_remesh"] = round(time.time() - t0, 1)
        result["files"]["remeshed"] = str(remeshed_file)
    except Exception as e:
        result["errors"].append(f"stage2: {e}")
        console.print(f"[red]Stage 2 failed: {e}[/red]")
        return result

    # Stage 3A: Tripo rig + animate
    t0 = time.time()
    try:
        rig_result = stage3a_rig_tripo.run(remeshed_file, output_dir)
        result["timings"]["stage3_rig"] = round(time.time() - t0, 1)
        result["files"]["rigged"] = str(rig_result.get("rigged", ""))
        result["files"]["animated"] = str(rig_result.get("animated", ""))
        result["rig_check"] = rig_result.get("check", {})
    except Exception as e:
        result["errors"].append(f"stage3: {e}")
        console.print(f"[red]Stage 3 failed: {e}[/red]")
        return result

    # Stage 4: Animation passthrough
    animated_path = rig_result.get("animated")
    if animated_path:
        try:
            final = stage4_animate.run(animated_path, output_dir)
            result["files"]["final"] = str(final)
        except Exception as e:
            result["errors"].append(f"stage4: {e}")

    result["total_time"] = round(sum(result["timings"].values()), 1)
    return result


def print_summary(results: list[dict]):
    """Print a summary table of all pipeline runs."""
    table = Table(title="Pipeline Results")
    table.add_column("Image", style="cyan", max_width=40)
    table.add_column("S1 (s)")
    table.add_column("S2 (s)")
    table.add_column("S3 (s)")
    table.add_column("Total (s)")
    table.add_column("Status")

    for r in results:
        status = "[green]OK[/green]" if not r["errors"] else f"[red]{len(r['errors'])} errors[/red]"
        t = r.get("timings", {})
        table.add_row(
            r["image_url"][-40:],
            str(t.get("stage1_seed3d", "-")),
            str(t.get("stage2_remesh", "-")),
            str(t.get("stage3_rig", "-")),
            str(r.get("total_time", "-")),
            status,
        )

    console.print(table)


@click.command()
@click.option("--image", help="Image URL or local path")
@click.option("--batch", help="Directory of images to process", type=click.Path(exists=True))
@click.option("--output-dir", default=None, help="Output directory", type=click.Path())
def main(image: str | None, batch: str | None, output_dir: str | None):
    """Run the full pet photo → animated 3D pipeline."""
    out = Path(output_dir) if output_dir else config.output_dir
    out.mkdir(parents=True, exist_ok=True)

    results = []

    if image:
        console.rule(f"[bold]Processing: {image}")
        r = run_single(image, out)
        results.append(r)

    elif batch:
        batch_dir = Path(batch)
        images = sorted(
            p for p in batch_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )
        console.print(f"Found {len(images)} images in {batch_dir}")
        for img_path in images:
            console.rule(f"[bold]Processing: {img_path.name}")
            r = run_single(str(img_path), out)
            results.append(r)
    else:
        console.print("[red]Provide --image or --batch[/red]")
        raise click.UsageError("Provide --image or --batch")

    print_summary(results)

    report_path = out / "pipeline_report.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    console.print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
