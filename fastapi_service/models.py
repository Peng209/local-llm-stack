"""SQLModel 表：用户、对话、消息。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=_new_uuid, primary_key=True, max_length=36)
    email: str = Field(max_length=255, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: str = Field(default_factory=_new_uuid, primary_key=True, max_length=36)
    user_id: str = Field(foreign_key="users.id", index=True, max_length=36)
    title: str = Field(default="新对话", max_length=256)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_seq", "conversation_id", "seq"),
    )

    id: str = Field(default_factory=_new_uuid, primary_key=True, max_length=36)
    conversation_id: str = Field(
        foreign_key="conversations.id", index=True, max_length=36
    )
    role: str = Field(max_length=32)
    content: str = Field(sa_column=Column(Text, nullable=False))
    seq: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
