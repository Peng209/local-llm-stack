"""对话 CRUD。"""

from __future__ import annotations

from fastapi import APIRouter, status

from fastapi_service import conversation_service
from fastapi_service.deps import CurrentUser, DbSession
from fastapi_service.schemas.conversation import (
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    session: DbSession, user: CurrentUser
) -> list[ConversationSummary]:
    return await conversation_service.list_conversations(session, user)


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest, session: DbSession, user: CurrentUser
) -> ConversationSummary:
    return await conversation_service.create_conversation(session, user, body.title)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, session: DbSession, user: CurrentUser
) -> ConversationDetail:
    return await conversation_service.get_conversation(session, user, conversation_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str, session: DbSession, user: CurrentUser
) -> None:
    await conversation_service.delete_conversation(session, user, conversation_id)
