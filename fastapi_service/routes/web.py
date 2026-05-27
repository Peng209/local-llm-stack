"""浏览器公开 API：/api/config、/api/chat（需登录并落库）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_service import config, conversation_service, inference
from fastapi_service.db import async_session_factory
from fastapi_service.deps import CurrentUser, DbSession
from fastapi_service.models import User
from fastapi_service.schemas.conversation import ChatWithConversationRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Web"])


@router.get("/config")
async def web_config() -> dict[str, Any]:
    return {
        "model": config.VLLM_MODEL,
        "maxContextTokens": config.VLLM_MAX_MODEL_LEN,
    }


@router.post("/chat", response_model=None)
async def api_chat(
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> Response | StreamingResponse | JSONResponse:
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    try:
        req = ChatWithConversationRequest.model_validate(body)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    return await _chat_persisted(request, session, user, req)


async def _chat_persisted(
    request: Request,
    session: AsyncSession,
    user: User,
    req: ChatWithConversationRequest,
) -> Response | StreamingResponse | JSONResponse:
    text = req.message.strip()
    voice_inputs = (
        [v.model_dump(exclude_none=True) for v in req.voice_inputs]
        if req.voice_inputs
        else None
    )
    stored = conversation_service.format_user_content(
        text,
        image_urls=req.image_urls,
        voice_count=len(voice_inputs or []),
    )

    conv, history = await conversation_service.append_user_message(
        session,
        user,
        conversation_id=req.conversation_id,
        content=stored,
    )
    conv_id = conv.id

    messages = inference.build_messages(
        history=history,
        image_urls=req.image_urls,
        voice_inputs=voice_inputs,
    )
    payload = inference.build_payload(
        messages=messages,
        model=None,
        stream=req.stream,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        top_p=req.top_p,
        enable_thinking=req.enable_thinking,
    )

    # 释放请求级 DB 会话，避免同步 vLLM 阻塞事件循环时占用连接导致死锁
    await session.close()

    if not req.stream:
        try:
            content, code, media = await inference.complete(payload)
        except inference.InferenceError as exc:
            logger.warning("推理失败: %s", exc.detail)
            async with async_session_factory() as db:
                await conversation_service.remove_last_user_message(db, conv_id)
            return JSONResponse({"error": exc.detail}, status_code=503)
        except Exception:
            logger.exception("推理未捕获异常")
            async with async_session_factory() as db:
                await conversation_service.remove_last_user_message(db, conv_id)
            return JSONResponse(
                {"error": "推理服务暂时不可用，请稍后重试"},
                status_code=503,
            )
        try:
            data = json.loads(content)
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(reply, str) and reply.strip():
                async with async_session_factory() as db:
                    await conversation_service.append_assistant_message(
                        db, conv_id, reply
                    )
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
        headers = {"X-Conversation-Id": conv_id}
        return Response(content=content, status_code=code, media_type=media, headers=headers)

    async def gen() -> Any:
        full = ""
        # 立刻发出首包，确保 Nginx/ngrok 收到合法 SSE 头与 body
        yield b": connected\n\n"
        try:
            async for chunk in inference.stream(payload):
                if await request.is_disconnected():
                    if full.strip():
                        async with async_session_factory() as db:
                            await conversation_service.append_assistant_message(
                                db, conv_id, full
                            )
                    return
                yield chunk
                if chunk.startswith(b"data:"):
                    line = chunk.decode("utf-8", errors="replace").strip()
                    if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]"):
                        try:
                            data = json.loads(line[5:].strip())
                            delta = data.get("choices", [{}])[0].get("delta", {}).get(
                                "content"
                            )
                            if isinstance(delta, str):
                                full += delta
                        except (json.JSONDecodeError, IndexError, KeyError):
                            pass
            if full.strip():
                async with async_session_factory() as db:
                    await conversation_service.append_assistant_message(
                        db, conv_id, full
                    )
        except inference.InferenceError as exc:
            logger.warning("流式推理失败: %s", exc.detail)
            async with async_session_factory() as db:
                await conversation_service.remove_last_user_message(db, conv_id)
            line = json.dumps(
                {"error": {"message": exc.detail[:2000], "type": "inference_error"}},
                ensure_ascii=False,
            )
            yield f"data: {line}\n\n".encode()
        except Exception:
            logger.exception("流式推理未捕获异常")
            async with async_session_factory() as db:
                await conversation_service.remove_last_user_message(db, conv_id)
            line = json.dumps(
                {
                    "error": {
                        "message": "推理服务暂时不可用，请稍后重试",
                        "type": "inference_error",
                    }
                },
                ensure_ascii=False,
            )
            yield f"data: {line}\n\n".encode()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": conv_id,
        },
    )
