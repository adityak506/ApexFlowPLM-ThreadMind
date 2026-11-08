"""Common response structures and helpers for MCP tools."""

from typing import Any
from pydantic import BaseModel


class MutationResult(BaseModel):
    """Normalized response schema for write/mutation tools enforcing dry-run safety."""

    success: bool
    is_dry_run: bool
    action: str
    message: str
    preview_data: dict[str, Any] | None = None
    applied_data: dict[str, Any] | None = None

