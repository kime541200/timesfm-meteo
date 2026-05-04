from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: UUID
    type: str
    status: str
    params: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class JobCreatedResponse(BaseModel):
    job_id: UUID
    status: str = "pending"
