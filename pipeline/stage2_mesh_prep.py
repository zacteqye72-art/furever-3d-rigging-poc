"""Stage 2: Mesh preparation — quad remesh via Tripo on fal.ai.

Takes the pet photo and generates a clean quad-remeshed 3D model via
Tripo v2.5 on fal.ai. This serves as both an alternative 3D generation
path and the mesh cleanup step.
"""

import os
from pathlib import Path

import fal_client
from rich.console import Console

from config import config

console = Console()


def _ensure_fal_key():
    if not os.environ.get("FAL_KEY") and config.fal.api_key:
        os.environ["FAL_KEY"] = config.fal.api_key


def generate_remeshed(image_url: str) -> dict:
    """Generate a quad-remeshed 3D model from an image via fal.ai Tripo."""
    _ensure_fal_key()

    arguments = {
        "image_url": image_url,
        "texture": config.mesh_prep.texture,
        "texture_alignment": config.mesh_prep.texture_alignment,
        "orientation": config.mesh_prep.orientation,
        "face_limit": config.mesh_prep.face_limit,
        "quad": config.mesh_prep.quad,
        "pbr": config.mesh_prep.pbr,
        "auto_size": config.mesh_prep.auto_size,
    }

    console.print(f"  fal.ai model: [cyan]{config.fal.tripo_image_to_3d}[/cyan]")
    console.print(f"  quad={arguments['quad']}, face_limit={arguments['face_limit']}")

    def on_queue_update(update):
        if hasattr(update, "logs"):
            for log in update.logs:
                console.print(f"    [dim]{log.get('message', log)}[/dim]")

    result = fal_client.subscribe(
        config.fal.tripo_image_to_3d,
        arguments=arguments,
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    return result


def download_mesh(result: dict, output_dir: Path, prefix: str = "mesh") -> Path:
    """Download the GLB mesh from fal.ai result."""
    import httpx

    output_dir.mkdir(parents=True, exist_ok=True)

    model_mesh = result.get("model_mesh") or result.get("pbr_model") or result.get("base_model")
    if not model_mesh:
        raise RuntimeError(f"No model_mesh in result: {list(result.keys())}")

    mesh_url = model_mesh["url"]
    task_id = result.get("task_id", "unknown")
    ext = "fbx" if config.mesh_prep.quad else "glb"
    out_path = output_dir / f"{prefix}_{task_id}.{ext}"

    console.print(f"  downloading → {out_path.name}")
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        resp = client.get(mesh_url)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)

    console.print(f"[green]Downloaded:[/green] {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")
    return out_path


def run(image_url: str, output_dir: Path | None = None) -> Path:
    """Full Stage 2: image → quad-remeshed 3D mesh."""
    output_dir = output_dir or config.output_dir
    console.rule("[bold]Stage 2: Mesh Prep (fal.ai Tripo quad remesh)")
    result = generate_remeshed(image_url)
    return download_mesh(result, output_dir, prefix="remeshed")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.stage2_mesh_prep <image_url>")
        sys.exit(1)
    result = run(sys.argv[1])
    print(f"Output: {result}")
