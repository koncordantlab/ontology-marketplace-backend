from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, timezone
import uuid


VALID_EMOJIS = ["👍", "👎", "❤️", "😂", "🎉", "🔥"]


class NewComment(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Comment content cannot be blank")
        return v.strip()


class Comment(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    author_email: Optional[str] = None
    author_name: Optional[str] = None
    reply_count: int = 0
    reactions: dict = Field(default_factory=dict)
    is_editable: bool = False

    @classmethod
    def from_new_comment(cls, new_comment: NewComment, author_email: str = None) -> "Comment":
        return cls(content=new_comment.content, author_email=author_email)


class NewReaction(BaseModel):
    emoji: str

    @field_validator("emoji")
    @classmethod
    def emoji_must_be_valid(cls, v: str) -> str:
        if v not in VALID_EMOJIS:
            raise ValueError(f"Invalid emoji. Must be one of: {', '.join(VALID_EMOJIS)}")
        return v


class NewReply(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Reply content cannot be blank")
        return v.strip()
