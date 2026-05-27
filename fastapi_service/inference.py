"""本进程 vLLM：加载模型、组装 messages、执行 chat 推理。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi_service import config

_LOG = logging.getLogger(__name__)
_GIB = 1024**3
_THINKING_RE = re.compile(
    r"<think>[\s\S]*?(?:</think>|\Z)",
    re.DOTALL,
)

_init_lock = threading.Lock()
_inference_lock = threading.Lock()
_state_lock = threading.Lock()
_llm: Any = None
_processor: Any = None
_model_id: str | None = None
_engine_state: str = "idle"  # idle | loading | ready | error
_engine_error: str | None = None

_MODEL_ALIASES: dict[str, str] = {
    "qwen2-vl-2b": "Qwen/Qwen2-VL-2B-Instruct",
    "qwen2-vl-2b-instruct": "Qwen/Qwen2-VL-2B-Instruct",
}


def resolve_model_id(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return "Qwen/Qwen2-VL-2B-Instruct"
    key = raw.lower().replace("_", "-")
    if key in _MODEL_ALIASES:
        return _MODEL_ALIASES[key]
    if "/" not in raw:
        return _MODEL_ALIASES.get(key, raw)
    return raw


def is_vision_model(model_id: str | None = None) -> bool:
    mid = (model_id or _model_id or resolve_model_id(config.VLLM_MODEL)).lower()
    return "qwen2-vl" in mid or "qwen2_vl" in mid or "qvq" in mid


class InferenceError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _try_clear_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass


def _is_oom_error(exc: BaseException) -> bool:
    try:
        import torch

        if isinstance(exc, torch.cuda.OutOfMemoryError):
            return True
    except Exception:
        pass
    msg = str(exc).lower()
    return (
        "out of memory" in msg
        or "cuda out of memory" in msg
        or ("cuda" in msg and "memory" in msg)
    )


def _inference_error_from_exc(exc: BaseException) -> InferenceError:
    if isinstance(exc, InferenceError):
        return exc
    if _is_oom_error(exc):
        _LOG.error("GPU 显存不足: %s", exc, exc_info=exc)
        _try_clear_cuda_cache()
        return InferenceError("显存不足，请稍后重试或减少对话长度/图片数量")
    _LOG.exception("推理异常: %s", exc)
    msg = str(exc).strip() or exc.__class__.__name__
    return InferenceError(f"推理失败: {msg[:500]}")


def engine_status() -> dict[str, str | None]:
    with _state_lock:
        return {"engine": _engine_state, "engine_error": _engine_error}


def _set_engine_state(state: str, error: str | None = None) -> None:
    global _engine_state, _engine_error
    with _state_lock:
        _engine_state = state
        _engine_error = error


def preload_engine() -> None:
    """启动时预加载 vLLM；Processor 在首次视觉推理时再加载。"""
    with _state_lock:
        if _engine_state == "ready":
            return
    try:
        _get_llm()
    except InferenceError:
        raise
    except Exception as exc:
        raise _inference_error_from_exc(exc) from exc


async def preload_async() -> None:
    # WSL 下 vLLM 使用 spawn，须在主线程初始化；勿放 asyncio.to_thread
    preload_engine()


def _gpu_memory_utilization() -> float:
    requested = float(config.VLLM_GPU_MEMORY_UTILIZATION)
    return max(0.05, min(1.0, requested))


def _get_llm() -> Any:
    global _llm, _model_id
    with _init_lock:
        if _llm is not None:
            _set_engine_state("ready")
            return _llm
        with _state_lock:
            if _engine_state == "idle":
                _set_engine_state("loading")
        try:
            from vllm import LLM
        except ImportError as exc:
            _set_engine_state("error", "未安装 vllm")
            raise InferenceError("未安装 vllm") from exc
        model_id = resolve_model_id(config.VLLM_MODEL)
        _model_id = model_id
        gpu_util = _gpu_memory_utilization()
        _LOG.info(
            "加载 vLLM: %s（util=%.2f, offline=%s）",
            model_id,
            gpu_util,
            os.environ.get("HF_HUB_OFFLINE", ""),
        )
        # 与 test/vllm-test.py 保持一致，避免 WSL 下额外参数导致初始化挂起
        llm_kw: dict[str, Any] = {
            "model": model_id,
            "trust_remote_code": True,
            "gpu_memory_utilization": gpu_util,
            "enforce_eager": True,
            "max_model_len": config.VLLM_MAX_MODEL_LEN,
            "kv_cache_memory_bytes": int(config.VLLM_KV_CACHE_MEMORY_BYTES),
        }
        try:
            _llm = LLM(**llm_kw)
        except Exception as exc:
            detail = f"引擎初始化失败: {exc}"
            _set_engine_state("error", detail[:500])
            raise InferenceError(detail) from exc
        _set_engine_state("ready")
        return _llm


def _get_processor() -> Any:
    global _processor, _model_id
    if _processor is not None:
        return _processor
    if not is_vision_model():
        raise InferenceError("当前模型非视觉模型，无法加载 processor")
    _get_llm()
    try:
        from transformers import AutoProcessor
    except ImportError as exc:
        raise InferenceError("未安装 transformers") from exc
    model_id = _model_id or resolve_model_id(config.VLLM_MODEL)
    _LOG.info("加载 Processor: %s", model_id)
    try:
        _processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    except Exception as exc:
        raise InferenceError(f"Processor 加载失败: {exc}") from exc
    return _processor


# --- messages ---


def _content_to_parts(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [dict(p) if isinstance(p, Mapping) else p for p in content]
    return [{"type": "text", "text": str(content)}]


def _merge_media(
    messages: list[dict[str, Any]],
    *,
    image_urls: list[str] | None,
    voice_inputs: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not image_urls and not voice_inputs:
        return messages
    out = [dict(m) for m in messages]
    for idx in range(len(out) - 1, -1, -1):
        if out[idx].get("role") == "user":
            parts = _content_to_parts(out[idx].get("content"))
            for url in image_urls or []:
                u = (url or "").strip()
                if u:
                    parts.append({"type": "image_url", "image_url": {"url": u}})
            for item in voice_inputs or []:
                if not isinstance(item, Mapping):
                    continue
                data = item.get("base64") or item.get("data")
                if isinstance(data, str) and data:
                    parts.append(
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": data,
                                "format": str(
                                    item.get("format") or item.get("mime") or "wav"
                                ),
                            },
                        }
                    )
            out[idx]["content"] = parts
            return out
    return out


def build_messages(
    *,
    user_message: str | None = None,
    history: list[dict[str, Any]] | None = None,
    system_prompt: str | None = None,
    image_urls: list[str] | None = None,
    voice_inputs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if history:
        msgs = [dict(m) for m in history]
    else:
        msgs = [{"role": "user", "content": (user_message or "").strip()}]
    if system_prompt:
        msgs.insert(0, {"role": "system", "content": system_prompt})
    return _merge_media(msgs, image_urls=image_urls, voice_inputs=voice_inputs)


def build_payload(
    *,
    messages: list[dict[str, Any]],
    model: str | None,
    stream: bool,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    enable_thinking: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model or config.VLLM_MODEL,
        "messages": messages,
        "stream": stream,
        "max_tokens": max_tokens
        if max_tokens is not None
        else config.DEFAULT_MAX_TOKENS,
        "enable_thinking": enable_thinking,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if extra:
        payload.update({k: v for k, v in extra.items() if k not in payload})
    return payload


# --- run inference ---


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits: list[str] = []
        for part in content:
            if not isinstance(part, Mapping):
                bits.append(str(part))
                continue
            ptype = part.get("type")
            if ptype == "text":
                bits.append(str(part.get("text", "")))
            elif ptype == "image_url":
                bits.append("[图片]")
            elif ptype == "input_audio":
                bits.append("[语音]")
            else:
                bits.append(json.dumps(part, ensure_ascii=False))
        return "\n".join(bits).strip()
    return str(content)


def _to_chat_format(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "role": str(m.get("role", "user")),
            "content": _flatten_content(m.get("content")),
        }
        for m in messages
    ]


def _to_qwen_vl_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OpenAI 风格 parts → Qwen2-VL chat template 消息。"""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = str(m.get("role", "user"))
        parts = _content_to_parts(m.get("content"))
        qwen_parts: list[dict[str, Any]] = []
        for p in parts:
            ptype = p.get("type")
            if ptype == "text":
                t = str(p.get("text", "")).strip()
                if t:
                    qwen_parts.append({"type": "text", "text": t})
            elif ptype == "image_url":
                url_obj = p.get("image_url")
                u = (
                    url_obj.get("url")
                    if isinstance(url_obj, Mapping)
                    else str(url_obj or "")
                )
                u = str(u).strip()
                if u:
                    qwen_parts.append({"type": "image", "image": u})
            elif ptype == "input_audio":
                qwen_parts.append({"type": "text", "text": "[语音]"})
            else:
                t = _flatten_content([p])
                if t:
                    qwen_parts.append({"type": "text", "text": t})
        if role == "assistant":
            text = _flatten_content(m.get("content"))
            out.append({"role": role, "content": text or ""})
            continue
        if not qwen_parts:
            qwen_parts = [{"type": "text", "text": ""}]
        out.append({"role": role, "content": qwen_parts})
    return out


def _prepare_vllm_vision_request(
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    from qwen_vl_utils import process_vision_info

    qwen_msgs = _to_qwen_vl_messages(messages)
    processor = _get_processor()
    prompt = processor.apply_chat_template(
        qwen_msgs,
        tokenize=False,
        add_generation_prompt=True,
    )
    patch_size = getattr(
        getattr(processor, "image_processor", None), "patch_size", 14
    )
    video_kwargs: dict[str, Any] | None = None
    try:
        image_inputs, video_inputs, video_kwargs = process_vision_info(
            qwen_msgs,
            image_patch_size=patch_size,
            return_video_kwargs=True,
            return_video_metadata=True,
        )
    except TypeError:
        image_inputs, video_inputs = process_vision_info(
            qwen_msgs, image_patch_size=patch_size
        )
    mm_data: dict[str, Any] = {}
    if image_inputs is not None:
        mm_data["image"] = image_inputs
    if video_inputs is not None:
        mm_data["video"] = video_inputs
    req: dict[str, Any] = {"prompt": prompt, "multi_modal_data": mm_data}
    if video_kwargs:
        req["mm_processor_kwargs"] = video_kwargs
    return req


def _strip_thinking(text: str) -> str:
    text = _THINKING_RE.sub("", text).strip()
    if "<think>" in text:
        text = text.split("<think>", 1)[0].strip()
    return text


def _sampling_params(payload: dict[str, Any]) -> Any:
    from vllm import SamplingParams

    sp_kw: dict[str, Any] = {
        "max_tokens": int(payload.get("max_tokens") or config.DEFAULT_MAX_TOKENS),
        "temperature": float(payload["temperature"])
        if payload.get("temperature") is not None
        else 0.7,
    }
    if payload.get("top_p") is not None:
        sp_kw["top_p"] = float(payload["top_p"])
    return SamplingParams(**sp_kw)


def _usage_from_output(req_out: Any, comp: Any, text: str) -> dict[str, int]:
    p_ids = getattr(req_out, "prompt_token_ids", None)
    c_ids = getattr(comp, "token_ids", None)
    if p_ids is not None and c_ids is not None:
        p, c = len(p_ids), len(c_ids)
        return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}
    c = max(1, len(text) // 4)
    return {"prompt_tokens": 0, "completion_tokens": c, "total_tokens": c}


def _run_chat_text(payload: dict[str, Any], messages: list[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    thinking = bool(payload.get("enable_thinking", False))
    llm = _get_llm()
    sp = _sampling_params(payload)
    chat_kw = {"chat_template_kwargs": {"enable_thinking": thinking}}
    try:
        outputs = llm.chat(
            _to_chat_format([dict(m) for m in messages]),
            sampling_params=sp,
            use_tqdm=False,
            **chat_kw,
        )
    except TypeError:
        outputs = llm.chat(
            _to_chat_format([dict(m) for m in messages]),
            sampling_params=sp,
            use_tqdm=False,
        )
    if not outputs or not getattr(outputs[0], "outputs", None):
        raise InferenceError("无模型输出")
    req_out = outputs[0]
    comp = req_out.outputs[0]
    text = str(getattr(comp, "text", "") or "")
    if not thinking:
        text = _strip_thinking(text)
    return text, _usage_from_output(req_out, comp, text)


def _run_chat_vision(payload: dict[str, Any], messages: list[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    llm = _get_llm()
    sp = _sampling_params(payload)
    try:
        llm_input = _prepare_vllm_vision_request([dict(m) for m in messages])
        outputs = llm.generate([llm_input], sampling_params=sp, use_tqdm=False)
    except InferenceError:
        raise
    except Exception as exc:
        raise InferenceError(f"视觉推理失败: {exc}") from exc
    if not outputs or not getattr(outputs[0], "outputs", None):
        raise InferenceError("无模型输出")
    req_out = outputs[0]
    comp = req_out.outputs[0]
    text = str(getattr(comp, "text", "") or "").strip()
    text = _strip_thinking(text)
    return text, _usage_from_output(req_out, comp, text)


def _run_chat(payload: dict[str, Any]) -> tuple[str, dict[str, int]]:
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise InferenceError("缺少 messages")

    if is_vision_model():
        return _run_chat_vision(payload, messages)
    return _run_chat_text(payload, messages)


def _run_chat_exclusive(payload: dict[str, Any]) -> tuple[str, dict[str, int]]:
    """单 GPU 串行推理：同一时刻仅一条请求占用 vLLM。"""
    with _inference_lock:
        try:
            return _run_chat(payload)
        except InferenceError:
            raise
        except Exception as exc:
            raise _inference_error_from_exc(exc) from exc


def _completion_json(
    payload: dict[str, Any], text: str, usage: dict[str, int]
) -> bytes:
    body = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": str(payload.get("model") or config.VLLM_MODEL),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
    }
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def _sse_chunks(payload: dict[str, Any], text: str) -> list[bytes]:
    model = str(payload.get("model") or config.VLLM_MODEL)
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    step = config.STREAM_CHUNK_CHARS
    chunks: list[bytes] = []
    for i in range(0, len(text), step):
        piece = text[i : i + step]
        delta: dict[str, Any] = {
            "id": cid,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {"index": 0, "delta": {"content": piece}, "finish_reason": None}
            ],
        }
        if i == 0:
            delta["choices"][0]["delta"]["role"] = "assistant"
        chunks.append(f"data: {json.dumps(delta, ensure_ascii=False)}\n\n".encode())
    end = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    chunks.append(f"data: {json.dumps(end, ensure_ascii=False)}\n\n".encode())
    chunks.append(b"data: [DONE]\n\n")
    return chunks


async def complete(payload: dict[str, Any]) -> tuple[bytes, int, str]:
    def _work() -> tuple[bytes, int, str]:
        try:
            text, usage = _run_chat_exclusive(payload)
        except InferenceError:
            raise
        except Exception as exc:
            raise _inference_error_from_exc(exc) from exc
        return (
            _completion_json(payload, text, usage),
            200,
            "application/json; charset=utf-8",
        )

    try:
        return await asyncio.to_thread(_work)
    except InferenceError:
        raise
    except Exception as exc:
        raise _inference_error_from_exc(exc) from exc


_SSE_KEEPALIVE = b": keep-alive\n\n"
_SSE_KEEPALIVE_INTERVAL_SEC = 10.0


async def stream(payload: dict[str, Any]) -> AsyncIterator[bytes]:
    """流式输出；推理完成前先周期性发送 SSE 注释，避免代理/ngrok 因长时间无字节而断连。"""

    yield _SSE_KEEPALIVE

    task = asyncio.create_task(asyncio.to_thread(_run_chat_exclusive, payload))
    try:
        while not task.done():
            _done, _pending = await asyncio.wait(
                {task}, timeout=_SSE_KEEPALIVE_INTERVAL_SEC
            )
            if not _done:
                yield _SSE_KEEPALIVE

        text, _usage = task.result()
    except InferenceError:
        raise
    except Exception as exc:
        raise _inference_error_from_exc(exc) from exc

    delay = float(config.STREAM_CHUNK_DELAY_SEC)
    for part in _sse_chunks(payload, text):
        yield part
        if delay > 0:
            await asyncio.sleep(delay)
