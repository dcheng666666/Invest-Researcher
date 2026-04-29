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
