from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent


class ArkConfig(BaseModel):
    """火山引擎方舟 — Seed3D-2.0 图生3D"""
    api_key: str = os.getenv("ARK_API_KEY", "")
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    model: str = "doubao-seed3d-2-0-250423"
    subdivision_level: str = "medium"
    file_format: str = "glb"


class FalConfig(BaseModel):
    """fal.ai — Tripo 重拓扑"""
    api_key: str = os.getenv("FAL_KEY", "")
    tripo_image_to_3d: str = "tripo3d/tripo/v2.5/image-to-3d"


class TripoConfig(BaseModel):
    """Tripo 官方 API — 绑骨 + 动画重定向"""
    api_key: str = os.getenv("TRIPO_API_KEY", "")
    base_url: str = "https://api.tripo3d.ai/v2/openapi"


class MeshPrepConfig(BaseModel):
    """fal.ai Tripo 端点参数"""
    texture: str = "standard"
    texture_alignment: str = "original_image"
    orientation: str = "default"
    face_limit: int = 10000
    quad: bool = True
    pbr: bool = True
    auto_size: bool = True


class PipelineConfig(BaseModel):
    ark: ArkConfig = ArkConfig()
    fal: FalConfig = FalConfig()
    tripo: TripoConfig = TripoConfig()
    mesh_prep: MeshPrepConfig = MeshPrepConfig()
    output_dir: Path = BASE_DIR / "test_assets" / "results_tripo"
    poll_interval: float = 3.0
    max_poll_attempts: int = 200


config = PipelineConfig()
