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


class ValuationScreenRowItem(BaseModel):
    """One row from valuation screening table (denormalized for list UI)."""

    refresh_date: str
    market: str
    code: str
    name: str
    board: str
    overall_score: float | None = None
    overall_verdict: str | None = None
    step_scores: list[int] | None = None
    valuation_score: int | None = None
    valuation_verdict: str | None = None
    pe_percentile: float | None = None
    peg: float | None = None
    current_pe: float | None = None
    step_errors: dict[str, str] = {}
    error: str | None = None


class ValuationScreenListResponse(BaseModel):
    """Paginated screening list with resolved refresh date."""

    refresh_date: str | None
    total: int
    items: list[ValuationScreenRowItem]
    completed_refresh_dates: list[str] = []


class ValuationScreenMetaResponse(BaseModel):
    """Latest completed refresh; ``completed_refresh_dates`` lists days that have row data (partial or complete)."""

    latest_completed_refresh_date: str | None
    completed_refresh_dates: list[str]
