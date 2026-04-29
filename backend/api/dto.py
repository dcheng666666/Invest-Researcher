"""Pydantic request/response DTOs for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel


class StockSearchResult(BaseModel):
    code: str
    name: str
    market: str


class SearchResponse(BaseModel):
    results: list[StockSearchResult]


class AnalysisEvent(BaseModel):
    step: int
    title: str
    status: str  # "running" | "completed" | "error"
    data: dict | None = None
    error: str | None = None


class PeriodMetric(BaseModel):
    """Serialization-friendly ``(period, value)`` row consumed by step DTOs."""

    period: str
    value: float


class AnnualRevenueChartPoint(BaseModel):
    """One bar per fiscal period: full-year revenue or YTD cumulative if FY not closed."""

    period: str
    value: float
    is_partial: bool = False
    partial_through: str | None = None
