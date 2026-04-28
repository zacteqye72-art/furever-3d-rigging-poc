"""Stage 1: Image → 3D model via Seed3D-2.0 on Volcano Engine Ark.

Async task flow: create task → poll until succeeded → return download URL.
"""

import time
from pathlib import Path

import httpx
from rich.console import Console

from config import config

console = Console()

TASK_URL = f"{config.ark.base_url}/content-generation/tasks"
HEADERS = {
    "Authorization": f"Bearer {config.ark.api_key}",
    "Content-Type": "application/json",
}


def _build_params_text() -> str:
    parts = []
    if config.ark.subdivision_level:
        parts.append(f"subdivisionlevel {config.ark.subdivision_level}")
    if config.ark.file_format:
        parts.append(f"fileformat {config.ark.file_format}")
    return "\n".join(parts) if parts else ""


def create_task(image_url: str) -> str:
    """Submit an image-to-3D generation task. Returns task_id."""
    content = [{"type": "image_url", "image_url": {"url": image_url}}]
    params_text = _build_params_text()
    if params_text:
        content.append({"type": "text", "text": params_text})

    payload = {
        "model": config.ark.model,
        "content": content,
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(TASK_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

    task_id = data.get("id")
    if not task_id:
        raise RuntimeError(f"No task_id in response: {data}")
    console.print(f"[green]Seed3D task created:[/green] {task_id}")
    return task_id


def poll_task(task_id: str) -> dict:
    """Poll until task succeeds or fails. Returns full response dict."""
    url = f"{TASK_URL}/{task_id}"

    with httpx.Client(timeout=30) as client:
        for attempt in range(config.max_poll_attempts):
            resp = client.get(url, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")

            if status == "succeeded":
                console.print(f"[green]Seed3D task succeeded[/green] ({attempt + 1} polls)")
                return data
            elif status in ("failed", "cancelled"):
                raise RuntimeError(f"Seed3D task {status}: {data}")

            console.print(f"  polling [{attempt + 1}] status={status}")
            time.sleep(config.poll_interval)

    raise TimeoutError(f"Seed3D task {task_id} did not complete in time")


def download_result(data: dict, output_dir: Path) -> Path:
    """Download the 3D file from task result. Returns local file path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    content = data.get("content", {})
    file_url = content.get("file_url") or content.get("video_url", "")
    if not file_url:
        raise RuntimeError(f"No file_url in task result: {data}")

    task_id = data.get("id", "unknown")
    ext = config.ark.file_format
    out_path = output_dir / f"{task_id}.{ext}"

    console.print(f"  downloading → {out_path.name}")
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        resp = client.get(file_url)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)

    console.print(f"[green]Downloaded:[/green] {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")
    return out_path


def run(image_url: str, output_dir: Path | None = None) -> Path:
    """Full Stage 1: image URL → local 3D file."""
    output_dir = output_dir or config.output_dir
    console.rule("[bold]Stage 1: Image → 3D (Seed3D-2.0)")
    task_id = create_task(image_url)
    data = poll_task(task_id)
    return download_result(data, output_dir)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.stage1_image_to_3d <image_url>")
        sys.exit(1)
    result = run(sys.argv[1])
    print(f"Output: {result}")
