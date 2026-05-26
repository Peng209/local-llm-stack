#!/usr/bin/env python3
"""离线 chat 自测。与 FastAPI 共用 fastapi_service.config 配置。"""

from __future__ import annotations

from vllm import LLM, SamplingParams

from fastapi_service import config


def main() -> None:
    model = config.VLLM_MODEL
    print("Loading LLM:", model, flush=True)
    llm = LLM(
        model=model,
        trust_remote_code=True,
        gpu_memory_utilization=float(config.VLLM_GPU_MEMORY_UTILIZATION),
        enforce_eager=True,
        max_model_len=int(config.VLLM_MAX_MODEL_LEN),
        kv_cache_memory_bytes=int(config.VLLM_KV_CACHE_MEMORY_BYTES),
    )
    sp = SamplingParams(temperature=0.7, max_tokens=256)
    messages = [{"role": "user", "content": "用一句话解释天空为什么是蓝色的。"}]
    outputs = llm.chat(
        messages,
        sampling_params=sp,
        use_tqdm=False,
        chat_template_kwargs={"enable_thinking": False},
    )
    print(outputs[0].outputs[0].text, flush=True)


if __name__ == "__main__":
    main()
