from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class WorkLogCreate(BaseModel):
    title: str
    content: str
    category: str = "general"
    tags: list[str] = []
    date: Optional[str] = None


class WorkLogUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None


class WorkLogResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    tags: list[str]
    date: str
    created_at: str
    updated_at: str


class SearchResult(BaseModel):
    id: int
    title: str
    content: str
    category: str
    tags: list[str]
    date: str
    score: float


class WeeklyReportRequest(BaseModel):
    start_date: str
    end_date: str
    style: str = "professional"


class WeeklyReportResponse(BaseModel):
    report: str
    summary: str
    statistics: dict


class ChatRequest(BaseModel):
    question: str
    context_days: int = 30


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


class CategoryEnum(str, Enum):
    DEVELOPMENT = "development"
    MEETING = "meeting"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    GENERAL = "general"
    BUGFIX = "bugfix"
    REVIEW = "review"
