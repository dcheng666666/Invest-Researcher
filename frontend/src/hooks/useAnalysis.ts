import { useState, useCallback, useRef } from "react";
import { apiFetch } from "../lib/api";
import type { AnalysisState, StepEvent, CompleteEvent } from "../types";

function normalizeIndustry(raw: unknown): string | null {
  if (raw == null) return null;
  const s = String(raw).trim();
  return s.length > 0 ? s : null;
}

const QUOTA_EXCEEDED_MSG =
  "今日报告次数已达上限，需要升级会员才能继续使用。";

const initialState: AnalysisState = {
  stockName: "",
  stockCode: "",
  industry: null,
  steps: {},
  complete: null,
  loading: false,
  error: null,
  errorCode: null,
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
      `/api/analyze/${encodeURIComponent(code)}?${params.toString()}`,
      { withCredentials: true },
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
        error: null,
        errorCode: null,
      }));
      eventSource.close();
    });

    // Use a non-reserved SSE event name. Browser EventSource treats `event: error`
    // as conflicting with connection-level `error` (no MessageEvent.data), so
    // application errors are sent as `analysis_error` instead.
    eventSource.addEventListener("analysis_error", (e: MessageEvent) => {
      if (e.data) {
        const event = JSON.parse(e.data) as {
          error?: string;
          error_code?: string;
        };
        const isQuota = event.error_code === "quota_exceeded";
        const msg = isQuota ? QUOTA_EXCEEDED_MSG : event.error || "分析过程中出错";
        setState((prev) => ({
          ...prev,
          error: msg,
          errorCode: isQuota ? "quota_exceeded" : (event.error_code ?? null),
          loading: false,
        }));
      }
      eventSource.close();
    });

    eventSource.onerror = () => {
      void apiFetch("/api/auth/session")
        .then(async (r) => {
          if (!r.ok) return;
          const j = (await r.json()) as {
            auth_required?: boolean;
            authenticated?: boolean;
            report_daily_limit?: number | null;
            report_used_today?: number;
          };
          if (j.auth_required && !j.authenticated) {
            window.dispatchEvent(new CustomEvent("app:unauthorized"));
          }
          const lim = j.report_daily_limit;
          const used = j.report_used_today;
          if (
            lim != null &&
            typeof used === "number" &&
            used >= lim
          ) {
            setState((prev) => {
              if (!prev.loading) return prev;
              return {
                ...prev,
                loading: false,
                error: QUOTA_EXCEEDED_MSG,
                errorCode: "quota_exceeded",
              };
            });
            return;
          }
        })
        .catch(() => {});

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

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null, errorCode: null }));
  }, []);

  return { state, startAnalysis, reset, clearError };
}
