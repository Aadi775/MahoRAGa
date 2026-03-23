from typing import Optional
from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    name: str
    path: str
    description: Optional[str] = None
    created_at: str


class Session(BaseModel):
    id: str
    project_id: str
    summary: str
    files_touched: list[str] = Field(default_factory=list)
    started_at: str
    ended_at: Optional[str] = None


class Error(BaseModel):
    id: str
    project_id: str
    session_id: str
    message: str
    context: str
    file: str
    timestamp: str
    message_embedding: Optional[list[float]] = None


class Solution(BaseModel):
    id: str
    error_id: str
    description: str
    code_snippet: Optional[str] = None
    timestamp: str


class Concept(BaseModel):
    id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)


class DailyActivity(BaseModel):
    id: str
    date: str
    project_id: str
    summary: str
    session_ids: list[str] = Field(default_factory=list)
    errors_count: int = 0
