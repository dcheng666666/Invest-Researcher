"""FastAPI routes for stock search and analysis."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from backend.api.dto import (
    SearchResponse,
    StockSearchResult,
    ValuationScreenListResponse,
    ValuationScreenMetaResponse,
    ValuationScreenRowItem,
)
from backend.api.excel_export import export_rule_analysis_workbook
from backend.api.sse import complete_event, step_event
from backend.application.analysis import service as analysis_service
from backend.application.analysis.score_aggregator import (
    overall_verdict_from_mean,
    overall_verdict_sql_predicate,
)
from backend.application.analysis.step_registry import STEP_CONFIGS
from backend.infrastructure import sqlite_store
from backend.infrastructure.parsers import DEFAULT_WINDOW_YEARS
from backend.repositories import symbol_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


_SORT_WHITELIST = frozenset(
    {
        "overall_desc",
        "overall_asc",
        *(
            f"step{i}_{d}"
            for i in range(1, 6)
            for d in ("desc", "asc")
        ),
    }
)

_VALUATION_SORT_MAX_KEYS = 12


def parse_valuation_sort_clauses(sort: str) -> list[str]:
    """Comma-separated keys → ``ORDER BY`` chain (AND-style multi-key order)."""
    raw = (sort or "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return ["overall_desc"]
    if len(parts) > _VALUATION_SORT_MAX_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many sort keys (max {_VALUATION_SORT_MAX_KEYS})",
        )
    for p in parts:
        if p not in _SORT_WHITELIST:
            raise HTTPException(status_code=400, detail=f"Invalid sort: {p}")
    return parts


@router.get("/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=1)):
    results = await asyncio.to_thread(symbol_repository.search, q)
    return SearchResponse(results=[StockSearchResult(**r) for r in results])


@router.get("/valuation-screen/meta", response_model=ValuationScreenMetaResponse)
async def valuation_screen_meta(
    dates_limit: int = Query(30, ge=1, le=200),
):
    def _load() -> ValuationScreenMetaResponse:
        latest = sqlite_store.get_latest_completed_refresh_date()
        dates = sqlite_store.list_refresh_dates_having_rows(limit=dates_limit)
        return ValuationScreenMetaResponse(
            latest_completed_refresh_date=latest,
            completed_refresh_dates=dates,
        )

    return await asyncio.to_thread(_load)


@router.get("/valuation-screen", response_model=ValuationScreenListResponse)
async def valuation_screen(
    refresh_date: str | None = Query(
        None,
        description="YYYY-MM-DD; default: latest completed refresh",
    ),
    board: str = Query("all", description="all | STAR | CHINEXT"),
    overall_verdict: str | None = Query(
        None,
        description="excellent | good | neutral | warning | danger (综合分档)",
    ),
    min_step1: int | None = Query(None, ge=0, le=5),
    max_step1: int | None = Query(None, ge=0, le=5),
    min_step2: int | None = Query(None, ge=0, le=5),
    max_step2: int | None = Query(None, ge=0, le=5),
    min_step3: int | None = Query(None, ge=0, le=5),
    max_step3: int | None = Query(None, ge=0, le=5),
    min_step4: int | None = Query(None, ge=0, le=5),
    max_step4: int | None = Query(None, ge=0, le=5),
    min_step5: int | None = Query(None, ge=0, le=5),
    max_step5: int | None = Query(None, ge=0, le=5),
    sort: str = Query(
        "overall_desc",
        description="Comma-separated, e.g. overall_desc,step1_asc (multi-key ORDER BY)",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    sort_clauses = parse_valuation_sort_clauses(sort)

    def _load() -> ValuationScreenListResponse:
        rd = refresh_date.strip() if refresh_date else None
        if not rd:
            rd = sqlite_store.get_default_valuation_screen_refresh_date()
        dates = sqlite_store.list_refresh_dates_having_rows(limit=30)
        if rd is None:
            return ValuationScreenListResponse(
                refresh_date=None,
                total=0,
                items=[],
                completed_refresh_dates=dates,
            )
        b = board.strip().lower() if board else "all"
        board_arg = None if b in ("all", "") else b.upper()
        ov_raw = overall_verdict.strip().lower() if overall_verdict else None
        ov_sql = overall_verdict_sql_predicate(ov_raw) if ov_raw else None
        if ov_raw and ov_sql is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid overall_verdict: {overall_verdict}",
            )
        mins = (min_step1, min_step2, min_step3, min_step4, min_step5)
        maxs = (max_step1, max_step2, max_step3, max_step4, max_step5)
        step_bounds: list[tuple[int | None, int | None]] = list(zip(mins, maxs))
        if not any(lo is not None or hi is not None for lo, hi in step_bounds):
            step_bounds = None
        rows, total = sqlite_store.query_valuation_screen_rows(
            refresh_date=rd,
            board=board_arg,
            overall_verdict_sql=ov_sql,
            step_score_bounds=step_bounds,
            sort_clauses=sort_clauses,
            limit=limit,
            offset=offset,
        )
        items = [
            ValuationScreenRowItem(
                **{
                    **r,
                    "overall_verdict": overall_verdict_from_mean(r.get("overall_score")),
                }
            )
            for r in rows
        ]
        return ValuationScreenListResponse(
            refresh_date=rd,
            total=total,
            items=items,
            completed_refresh_dates=dates,
        )

    return await asyncio.to_thread(_load)


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
