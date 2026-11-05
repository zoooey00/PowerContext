from datetime import date as Date
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class WorkLogCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=2000)
    category: str = Field(default='general', max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=16)
    date: Date = Field(default_factory=Date.today)


class WorkLogUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    category: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = Field(default=None, max_length=16)


class WorkLogResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    tags: list[str]
    date: str
    created_at: str
    updated_at: str
    memory_ref: dict | None = None


class SearchResult(WorkLogResponse):
    score: float
    matched_by: list[str] = Field(default_factory=list)


class WeeklyReportRequest(BaseModel):
    start_date: Date
    end_date: Date
    style: Literal['professional', 'concise', 'detailed'] = 'professional'

    @model_validator(mode='after')
    def valid_range(self):
        if self.start_date > self.end_date:
            raise ValueError('开始日期必须早于或等于结束日期')
        return self


class WeeklyReportResponse(BaseModel):
    report: str
    summary: str
    statistics: dict
    memory_evidence: list[dict] = Field(default_factory=list)
    memory_context: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    context_days: int = Field(default=30, ge=1, le=366)


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
