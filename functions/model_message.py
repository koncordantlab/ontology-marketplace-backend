from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, timezone
import uuid


class NewMessage(BaseModel):
    recipient_fuid: str
    subject: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("subject")
    @classmethod
    def subject_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Subject cannot be blank")
        return v.strip()

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be blank")
        return v.strip()


class MessageReply(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be blank")
        return v.strip()


class Message(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject: str
    content: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sender_email: Optional[str] = None
    recipient_email: Optional[str] = None
