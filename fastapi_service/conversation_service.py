"""对话 CRUD 与消息持久化。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from fastapi_service.models import Conversation, Message, User
from fastapi_service.schemas.conversation import (
    ConversationDetail,
    ConversationSummary,
    MessageOut,
)


def _ts(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _title_from_message(text: str) -> str:
    t = text.strip()
    if len(t) <= 32:
        return t or "新对话"
    return t[:32] + "…"


def format_user_content(
    text: str,
    *,
    image_urls: list[str] | None = None,
    voice_count: int = 0,
) -> str:
    """持久化展示用文本（多模态以标记形式保存）。"""
    parts: list[str] = []
    t = text.strip()
    if t:
        parts.append(t)
    img_n = len([u for u in (image_urls or []) if (u or "").strip()])
    if img_n:
        parts.append(f"[图片×{img_n}]")
    if voice_count:
        parts.append(f"[语音×{voice_count}]")
    return "\n".join(parts) if parts else "新消息"


async def list_conversations(
    session: AsyncSession, user: User
) -> list[ConversationSummary]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(col(Conversation.updated_at).desc())
    )
    rows = result.scalars().all()
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=_ts(c.created_at),
            updated_at=_ts(c.updated_at),
        )
        for c in rows
    ]


async def get_conversation(
    session: AsyncSession, user: User, conversation_id: str
) -> ConversationDetail:
    conv = await _get_owned_conversation(session, user, conversation_id)
    messages = await _load_messages(session, conversation_id)
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        messages=messages,
        created_at=_ts(conv.created_at),
        updated_at=_ts(conv.updated_at),
    )


async def create_conversation(
    session: AsyncSession, user: User, title: str = "新对话"
) -> ConversationSummary:
    now = datetime.now(timezone.utc)
    conv = Conversation(user_id=user.id, title=title, created_at=now, updated_at=now)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        created_at=_ts(conv.created_at),
        updated_at=_ts(conv.updated_at),
    )


async def delete_conversation(
    session: AsyncSession, user: User, conversation_id: str
) -> None:
    conv = await _get_owned_conversation(session, user, conversation_id)
    await session.execute(
        delete(Message).where(Message.conversation_id == conv.id)
    )
    await session.delete(conv)
    await session.commit()


async def append_user_message(
    session: AsyncSession,
    user: User,
    *,
    conversation_id: str | None,
    content: str,
) -> tuple[Conversation, list[dict[str, str]]]:
    """写入用户消息并返回对话与完整 history（含本条）。"""
    now = datetime.now(timezone.utc)
    if conversation_id:
        conv = await _get_owned_conversation(session, user, conversation_id)
    else:
        conv = Conversation(
            user_id=user.id,
            title=_title_from_message(content),
            created_at=now,
            updated_at=now,
        )
        session.add(conv)
        await session.flush()

    next_seq = await _next_seq(session, conv.id)
    msg = Message(
        conversation_id=conv.id,
        role="user",
        content=content,
        seq=next_seq,
        created_at=now,
    )
    session.add(msg)

    if conv.title == "新对话":
        conv.title = _title_from_message(content)
    conv.updated_at = now
    session.add(conv)
    await session.commit()
    await session.refresh(conv)

    history = await _history_dicts(session, conv.id)
    return conv, history


async def append_assistant_message(
    session: AsyncSession,
    conversation_id: str,
    content: str,
) -> None:
    now = datetime.now(timezone.utc)
    next_seq = await _next_seq(session, conversation_id)
    session.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            seq=next_seq,
            created_at=now,
        )
    )
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        return
    conv.updated_at = now
    session.add(conv)
    await session.commit()


async def remove_last_user_message(
    session: AsyncSession, conversation_id: str
) -> None:
    """推理失败时回滚最后一条用户消息。"""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(col(Message.seq).desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if last is None or last.role != "user":
        return
    await session.delete(last)
    await session.commit()


async def _get_owned_conversation(
    session: AsyncSession, user: User, conversation_id: str
) -> Conversation:
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="对话不存在")
    return conv


async def _load_messages(session: AsyncSession, conversation_id: str) -> list[MessageOut]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(col(Message.seq).asc())
    )
    return [
        MessageOut(id=m.id, role=m.role, content=m.content, seq=m.seq)
        for m in result.scalars().all()
    ]


async def _history_dicts(
    session: AsyncSession, conversation_id: str
) -> list[dict[str, str]]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(col(Message.seq).asc())
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]


async def _next_seq(session: AsyncSession, conversation_id: str) -> int:
    result = await session.execute(
        select(Message.seq)
        .where(Message.conversation_id == conversation_id)
        .order_by(col(Message.seq).desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    return (last or 0) + 1
