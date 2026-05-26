"""对话与消息 API 模型。"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class VoiceInputBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    format: str | None = Field(
        default=None, validation_alias=AliasChoices("format", "mime")
    )
    base64: str | None = None
    data: str | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    seq: int


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: int
    updated_at: int


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[MessageOut]
    created_at: int
    updated_at: int


class CreateConversationRequest(BaseModel):
    title: str = Field(default="新对话", max_length=256)


class ChatWithConversationRequest(BaseModel):
    message: str = ""
    conversation_id: str | None = None
    stream: bool = True
    max_tokens: int = Field(default=512, ge=1, le=32768)
    temperature: float | None = None
    top_p: float | None = None
    enable_thinking: bool = False
    image_urls: list[str] | None = None
    voice_inputs: list[VoiceInputBlock] | None = None

    @model_validator(mode="after")
    def _require_content(self) -> ChatWithConversationRequest:
        has_text = bool(self.message.strip())
        has_img = bool(
            self.image_urls and any((u or "").strip() for u in self.image_urls)
        )
        has_voice = bool(
            self.voice_inputs
            and any(
                (v.base64 or v.data or "").strip()
                for v in self.voice_inputs
            )
        )
        if not (has_text or has_img or has_voice):
            raise ValueError("message、image_urls、voice_inputs 至少填一项")
        return self
