"""启动入口：主线程预加载 vLLM 后再启动 uvicorn（WSL spawn 要求）。"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
_LOG = logging.getLogger(__name__)


def _preload_vllm_main_thread() -> None:
    """与 test/vllm-test.py 相同方式加载，避免 inference 初始化路径在 WSL 上挂起。"""
    from vllm import LLM

    from fastapi_service import config, inference

    model = config.VLLM_MODEL
    util = max(0.05, min(1.0, float(config.VLLM_GPU_MEMORY_UTILIZATION)))
    _LOG.info("加载 vLLM: %s（util=%.2f）", model, util)
    llm = LLM(
        model=model,
        trust_remote_code=True,
        gpu_memory_utilization=util,
        enforce_eager=True,
        max_model_len=int(config.VLLM_MAX_MODEL_LEN),
        kv_cache_memory_bytes=int(config.VLLM_KV_CACHE_MEMORY_BYTES),
    )
    inference._llm = llm  # noqa: SLF001
    inference._model_id = model  # noqa: SLF001
    inference._set_engine_state("ready")


def main() -> None:
    from fastapi_service import config

    if config.VLLM_PRELOAD_AT_STARTUP:
        _LOG.info("主线程预加载 vLLM: %s", config.VLLM_MODEL)
        try:
            _preload_vllm_main_thread()
            _LOG.info("vLLM 预加载完成")
        except Exception as exc:
            _LOG.exception("vLLM 预加载失败: %s", exc)
            sys.exit(1)

    import uvicorn

    uvicorn.run(
        "fastapi_service.main:app",
        host="127.0.0.1",
        port=8101,
        log_level="info",
    )


if __name__ == "__main__":
    main()
