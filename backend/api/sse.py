"""SSE event payload helpers for the analysis stream endpoint."""

from __future__ import annotations

import json
from typing import Any


def step_event(
    step: int,
    title: str,
    status: str,
    *,
    data: dict[str, Any] | None = None,
    error: str | None = None,
    error_code: str | None = None,
) -> str:
    payload: dict[str, Any] = {"step": step, "title": title, "status": status}
    if data is not None:
        payload["data"] = data
    if error is not None:
        payload["error"] = error
    if error_code is not None:
        payload["error_code"] = error_code
    return json.dumps(payload, ensure_ascii=False)


def complete_event(
    *,
    overall_score: float,
    scores: list[int],
    stock_name: str,
    stock_code: str,
    industry: str | None = None,
) -> str:
    return json.dumps(
        {
            "overall_score": overall_score,
            "scores": scores,
            "stock_name": stock_name,
            "stock_code": stock_code,
            "industry": industry,
        },
        ensure_ascii=False,
    )
