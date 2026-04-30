"""FastAPI routes for stock search and analysis."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from backend.api.dto import SearchResponse, StockSearchResult
from backend.api.excel_export import export_rule_analysis_workbook
from backend.api.sse import complete_event, step_event
from backend.application.analysis import service as analysis_service
from backend.application.analysis.step_registry import STEP_CONFIGS
from backend.infrastructure.parsers import DEFAULT_WINDOW_YEARS
from backend.repositories import symbol_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=1)):
    results = await asyncio.to_thread(symbol_repository.search, q)
    return SearchResponse(results=[StockSearchResult(**r) for r in results])


async def _analysis_stream(code: str, window_years: int) -> AsyncGenerator[dict, None]:
    stock_name = await asyncio.to_thread(analysis_service.stock_display_name, code)

    yield {"event": "step", "data": step_event(0, "数据获取", "running")}

    ctx = await asyncio.to_thread(
        analysis_service.build_context, code, window_years=window_years
    )

    if ctx is None:
        yield {
            "event": "error",
            "data": step_event(
                0,
                "数据获取",
                "error",
                error="无法获取财务数据，请检查股票代码。",
            ),
        }
        return

    yield {
        "event": "step",
        "data": step_event(
            0,
            "数据获取",
            "completed",
            data={
                "stock_name": stock_name,
                "stock_code": code,
                "industry": ctx.industry,
            },
        ),
    }

    scores: list[int] = []
    for cfg in STEP_CONFIGS:
        yield {"event": "step", "data": step_event(cfg.number, cfg.title, "running")}
        try:
            await asyncio.sleep(0.5)
            result_model = await asyncio.to_thread(cfg.analyzer, ctx)
            result_data = result_model.model_dump()
            scores.append(int(result_data.get("score", 3)))
            yield {
                "event": "step",
                "data": step_event(
                    cfg.number, cfg.title, "completed", data=result_data
                ),
            }
        except Exception as e:
            logger.exception("Step %d failed", cfg.number)
            scores.append(0)
            yield {
                "event": "step",
                "data": step_event(cfg.number, cfg.title, "error", error=str(e)),
            }

    overall = analysis_service.overall_score(scores)
    yield {
        "event": "complete",
        "data": complete_event(
            overall_score=overall,
            scores=scores,
            stock_name=stock_name,
            stock_code=code,
            industry=ctx.industry,
        ),
    }


@router.get("/analyze/{code}")
async def analyze(
    code: str,
    window_years: int = Query(
        DEFAULT_WINDOW_YEARS, ge=3, le=20, description="Rolling history window in years"
    ),
):
    return EventSourceResponse(_analysis_stream(code, window_years))


def _build_excel_for_code(code: str, window_years: int) -> tuple[bytes, str] | None:
    ctx = analysis_service.build_context(code, window_years=window_years)
    if ctx is None:
        return None
    name = analysis_service.stock_display_name(code)
    results, errors, scores = analysis_service.run_steps(ctx)
    body = export_rule_analysis_workbook(code, name, results, errors, scores)
    safe = code.replace("/", "_").replace("\\", "_")
    return body, f"{safe}_analysis.xlsx"


@router.get("/analyze/{code}/excel")
async def analyze_excel(
    code: str,
    window_years: int = Query(
        DEFAULT_WINDOW_YEARS, ge=3, le=20, description="Rolling history window in years"
    ),
):
    """Run the same rule-based steps as the SSE flow and return a single .xlsx file."""
    payload = await asyncio.to_thread(_build_excel_for_code, code, window_years)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="无法获取财务数据，请检查股票代码。",
        )
    body, filename = payload
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
