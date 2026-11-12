from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorPayload(BaseModel):
    code: str
    message: str
    hint: str
    retryable: bool
    requires_user_input: bool
    retry_after_seconds: int | None = None
    candidates: list[str] = Field(default_factory=list)


class ListEnvelope(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
    truncated: bool
    items: list[Any]


class CategoryTreeNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    level: int
    is_system: bool
    sort_order: int
    children: list["CategoryTreeNode"] = Field(default_factory=list)


CategoryTreeNode.model_rebuild()
