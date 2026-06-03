"""应用配置：默认值在 Settings；密钥为空，由根目录 .env 覆盖。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 密钥（默认空，须在 .env 中填写）
    hf_token: str = ""
    internal_api_key: str = ""
    database_url: str = ""
    jwt_secret: str = ""
    ngrok_token: str = ""

    # 非密钥（可改代码默认值，也可用环境变量覆盖）
    hf_endpoint: str = "https://hf-mirror.com"
    hf_hub_offline: bool = False
    vllm_model: str = "Qwen/Qwen2-VL-2B-Instruct"
    vllm_gpu_memory_utilization: float = 0.45
    vllm_max_model_len: int = 4096
    vllm_limit_images_per_prompt: int = 4
    vllm_kv_cache_memory_bytes: int = 536_870_912
    vllm_default_max_tokens: int = 512
    local_vllm_stream_chunk_chars: int = 12
    local_vllm_stream_chunk_delay_sec: float = 0.02
    jwt_expire_minutes: int = 10_080
    httpx_timeout_seconds: int = 300
    db_echo: bool = False
    nginx_http_port: int = 80

    @field_validator("hf_hub_offline", mode="before")
    @classmethod
    def _parse_hf_hub_offline(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes")
        return bool(value)

    @field_validator("db_echo", mode="before")
    @classmethod
    def _parse_db_echo(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes")
        return bool(value)

    @field_validator("vllm_max_model_len")
    @classmethod
    def _min_max_model_len(cls, value: int) -> int:
        return max(512, value)

    @field_validator("vllm_limit_images_per_prompt")
    @classmethod
    def _min_limit_images(cls, value: int) -> int:
        return max(1, value)

    @field_validator("vllm_default_max_tokens", "local_vllm_stream_chunk_chars")
    @classmethod
    def _min_positive_int(cls, value: int) -> int:
        return max(1, value)

    @field_validator("jwt_expire_minutes")
    @classmethod
    def _min_jwt_expire(cls, value: int) -> int:
        return max(5, value)

    @field_validator("vllm_gpu_memory_utilization")
    @classmethod
    def _clamp_gpu_util(cls, value: float) -> float:
        return max(0.05, min(1.0, value))


def _apply_hf_env(settings: Settings) -> None:
    if settings.hf_endpoint:
        os.environ.setdefault("HF_ENDPOINT", settings.hf_endpoint)
    if settings.hf_token:
        os.environ["HF_TOKEN"] = settings.hf_token
    if settings.hf_hub_offline:
        os.environ["HF_HUB_OFFLINE"] = "1"


settings = Settings()
_apply_hf_env(settings)

# 模块级导出（保持现有 import config.VLLM_MODEL 用法）
VLLM_MODEL = settings.vllm_model
VLLM_MAX_MODEL_LEN = settings.vllm_max_model_len
VLLM_LIMIT_IMAGES_PER_PROMPT = settings.vllm_limit_images_per_prompt
VLLM_GPU_MEMORY_UTILIZATION = settings.vllm_gpu_memory_utilization
VLLM_KV_CACHE_MEMORY_BYTES = settings.vllm_kv_cache_memory_bytes
DEFAULT_MAX_TOKENS = settings.vllm_default_max_tokens
STREAM_CHUNK_CHARS = settings.local_vllm_stream_chunk_chars
STREAM_CHUNK_DELAY_SEC = settings.local_vllm_stream_chunk_delay_sec

DATABASE_URL = settings.database_url or (
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/my_vllm"
)
DB_ECHO = settings.db_echo

JWT_SECRET = settings.jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = settings.jwt_expire_minutes

HF_TOKEN = settings.hf_token
HF_ENDPOINT = settings.hf_endpoint
INTERNAL_API_KEY = settings.internal_api_key
NGROK_TOKEN = settings.ngrok_token

HTTPX_TIMEOUT_SECONDS = settings.httpx_timeout_seconds
NGINX_HTTP_PORT = settings.nginx_http_port
