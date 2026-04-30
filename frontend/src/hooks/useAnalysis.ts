import { useState, useCallback, useRef } from "react";
import type { AnalysisState, StepEvent, CompleteEvent } from "../types";

function normalizeIndustry(raw: unknown): string | null {
  if (raw == null) return null;
  const s = String(raw).trim();
  return s.length > 0 ? s : null;
}

const initialState: AnalysisState = {
  stockName: "",
  stockCode: "",
  industry: null,
  steps: {},
  complete: null,
  loading: false,
  error: null,
};

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>(initialState);
  const abortRef = useRef<AbortController | null>(null);

  const startAnalysis = useCallback((code: string, windowYears: number = 10) => {
    if (abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    abortRef.current = controller;

    setState({ ...initialState, loading: true, stockCode: code });

    const params = new URLSearchParams();
    params.set("window_years", String(windowYears));
    const eventSource = new EventSource(
      `/api/analyze/${encodeURIComponent(code)}?${params.toString()}`
    );

    eventSource.addEventListener("step", (e: MessageEvent) => {
      const event: StepEvent = JSON.parse(e.data);

      setState((prev) => {
        const updated = { ...prev, steps: { ...prev.steps } };

        if (event.step === 0 && event.status === "completed" && event.data) {
          const d = event.data as Record<string, unknown>;
          updated.stockName = String(d.stock_name ?? "");
          updated.stockCode = String(d.stock_code ?? "");
          updated.industry = normalizeIndustry(d.industry);
        }

        updated.steps[event.step] = event;
        return updated;
      });
    });

    eventSource.addEventListener("complete", (e: MessageEvent) => {
      const data: CompleteEvent = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        complete: data,
        loading: false,
        stockName: data.stock_name,
        industry:
          normalizeIndustry(data.industry) ?? prev.industry,
      }));
      eventSource.close();
    });

    eventSource.addEventListener("error", (e: MessageEvent) => {
      if (e.data) {
        const event = JSON.parse(e.data);
        setState((prev) => ({
          ...prev,
          error: event.error || "分析过程中出错",
          loading: false,
        }));
      }
      eventSource.close();
    });

    eventSource.onerror = () => {
      setState((prev) => {
        if (prev.loading) {
          return { ...prev, loading: false };
        }
        return prev;
      });
      eventSource.close();
    };

    controller.signal.addEventListener("abort", () => {
      eventSource.close();
    });
  }, []);

  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setState(initialState);
  }, []);

  return { state, startAnalysis, reset };
}
