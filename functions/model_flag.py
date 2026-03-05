from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime, timezone
import uuid

VALID_REASONS = ["spam", "harassment", "misinformation", "off-topic", "other"]


class NewFlag(BaseModel):
    reason: str
    details: Optional[str] = Field(None, max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_must_be_valid(cls, v: str) -> str:
        if v not in VALID_REASONS:
            raise ValueError(f"Invalid reason. Must be one of: {', '.join(VALID_REASONS)}")
        return v

    @model_validator(mode="after")
    def other_requires_details(self):
        if self.reason == "other" and (not self.details or not self.details.strip()):
            raise ValueError("Details are required when reason is 'other'")
        return self


class Flag(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reason: str
    details: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None
