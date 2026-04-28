"""Stage 3A: Auto-rig + animation via Tripo REST API.

Flow: upload model → check_riggable → rig_model → retarget_animation.
Uses raw REST calls (no SDK dependency) for transparency.
"""

import time
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console

from config import config

console = Console()

BASE = config.tripo.base_url
HEADERS = {
    "Authorization": f"Bearer {config.tripo.api_key}",
    "Content-Type": "application/json",
}


# ── helpers ──────────────────────────────────────────────────────────

def _post_task(payload: dict) -> str:
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{BASE}/task", json=payload, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
    task_id = data.get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"No task_id: {data}")
    return task_id


def _poll_task(task_id: str) -> dict:
    with httpx.Client(timeout=30) as c:
        for attempt in range(config.max_poll_attempts):
            r = c.get(f"{BASE}/task/{task_id}", headers=HEADERS)
            r.raise_for_status()
            data = r.json().get("data", {})
            status = data.get("status", "")

            if status == "success":
                console.print(f"  [green]task {task_id[:12]}… succeeded[/green] ({attempt + 1} polls)")
                return data
            elif status in ("failed", "cancelled", "banned"):
                raise RuntimeError(f"Task {task_id} {status}: {data}")

            console.print(f"    polling [{attempt + 1}] status={status}")
            time.sleep(config.poll_interval)

    raise TimeoutError(f"Task {task_id} timed out")


def _upload_file(file_path: Path) -> str:
    """Upload a local 3D file to Tripo and return a file_token."""
    with httpx.Client(timeout=120) as c:
        r = c.post(
            f"{BASE}/upload",
            headers={"Authorization": f"Bearer {config.tripo.api_key}"},
            files={"file": (file_path.name, file_path.read_bytes())},
        )
        r.raise_for_status()
        data = r.json()
    token = data.get("data", {}).get("image_token")
    if not token:
        raise RuntimeError(f"Upload failed: {data}")
    console.print(f"  [green]uploaded[/green] {file_path.name} → {token[:20]}…")
    return token


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=300, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    console.print(f"  [green]saved[/green] {dest.name} ({dest.stat().st_size / 1024:.0f} KB)")
    return dest


# ── pipeline steps ───────────────────────────────────────────────────

def check_riggable(model_task_id: str) -> dict:
    """Check if a model can be rigged."""
    console.print("  checking riggability…")
    tid = _post_task({
        "type": "check_riggable",
        "original_model_task_id": model_task_id,
    })
    data = _poll_task(tid)
    output = data.get("output", {})
    riggable = output.get("riggable", False)
    rig_type = output.get("rig_type", "unknown")
    console.print(f"  riggable={riggable}, rig_type={rig_type}")
    return {"riggable": riggable, "rig_type": rig_type}


def rig_model(
    model_task_id: str,
    rig_type: str = "quadruped",
    out_format: str = "glb",
    spec: str = "tripo",
) -> dict:
    """Auto-rig the model. Returns task data with output URLs."""
    console.print(f"  rigging (type={rig_type}, spec={spec})…")
    tid = _post_task({
        "type": "rig",
        "original_model_task_id": model_task_id,
        "out_format": out_format,
        "rig_type": rig_type,
        "spec": spec,
    })
    return _poll_task(tid)


def retarget_animation(
    model_task_id: str,
    animation: str | list[str] = "preset:quadruped:walk",
    out_format: str = "glb",
    bake: bool = True,
) -> dict:
    """Apply preset animation(s) to a rigged model."""
    if isinstance(animation, str):
        animation = [animation]
    console.print(f"  retargeting animation: {animation}")
    tid = _post_task({
        "type": "retarget",
        "original_model_task_id": model_task_id,
        "animation": animation,
        "out_format": out_format,
        "bake_animation": bake,
    })
    return _poll_task(tid)


def generate_and_rig(image_url: str) -> str:
    """Generate a 3D model from image via Tripo, return model task_id.

    Use this when you want Tripo to handle both generation and rigging,
    skipping Seed3D. The task_id can then be passed to rig_model / retarget.
    """
    console.print("  generating 3D model via Tripo API…")
    tid = _post_task({
        "type": "image_to_model",
        "file": {"type": "image_url", "url": image_url},
        "model_version": "v2.5",
        "texture": True,
        "pbr": True,
    })
    _poll_task(tid)
    return tid


# ── full stage runner ────────────────────────────────────────────────

def run(
    model_file: Path,
    output_dir: Path | None = None,
    rig_type: str = "quadruped",
    animations: list[str] | None = None,
) -> dict:
    """Full Stage 3A: local 3D file → rigged + animated GLB.

    Returns dict with paths to rigged and animated files.
    """
    output_dir = output_dir or config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    animations = animations or ["preset:quadruped:walk"]

    console.rule("[bold]Stage 3A: Auto-Rig (Tripo API)")

    # 1. Upload the model
    token = _upload_file(model_file)

    # 2. Create a conversion task to get a task_id Tripo can reference
    console.print("  converting uploaded file…")
    convert_tid = _post_task({
        "type": "upload_model",
        "file": {"type": "file_token", "file_token": token},
    })
    convert_data = _poll_task(convert_tid)
    model_task_id = convert_data.get("task_id", convert_tid)

    # 3. Check riggable
    rig_check = check_riggable(model_task_id)
    if not rig_check["riggable"]:
        console.print("[red]Model is not riggable[/red]")
        return {"rigged": None, "animated": None, "check": rig_check}

    detected_type = rig_check.get("rig_type", rig_type)
    if detected_type and detected_type != "unknown":
        rig_type = detected_type

    # 4. Rig
    rig_data = rig_model(model_task_id, rig_type=rig_type)
    rig_url = (rig_data.get("output", {}).get("model")
               or rig_data.get("output", {}).get("pbr_model", ""))
    rigged_path = None
    if rig_url:
        rigged_path = _download(rig_url, output_dir / f"rigged_{model_task_id[:12]}.glb")

    # 5. Retarget animation
    anim_data = retarget_animation(model_task_id, animation=animations)
    anim_url = (anim_data.get("output", {}).get("model")
                or anim_data.get("output", {}).get("pbr_model", ""))
    animated_path = None
    if anim_url:
        animated_path = _download(anim_url, output_dir / f"animated_{model_task_id[:12]}.glb")

    return {
        "rigged": rigged_path,
        "animated": animated_path,
        "check": rig_check,
        "model_task_id": model_task_id,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.stage3a_rig_tripo <model_file.glb>")
        sys.exit(1)
    result = run(Path(sys.argv[1]))
    print(f"Result: {result}")
