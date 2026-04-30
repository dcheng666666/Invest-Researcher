import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useParams, useNavigate, useOutletContext } from "react-router-dom";
import { useAnalysis } from "../hooks/useAnalysis";
import AnalysisReport from "../components/AnalysisReport";
import SearchBar from "../components/SearchBar";
import type { StockSearchResult } from "../types";
import type { OutletContext } from "../App";

const WINDOW_YEARS_STORAGE_KEY = "analysis_window_years";
const WINDOW_YEAR_OPTIONS = [3, 5, 7, 10, 12, 15, 20] as const;
const DEFAULT_WINDOW_YEARS = 10;

function parseSymbol(symbol: string): { market: string; code: string } | null {
  const match = symbol.match(/^(sh|sz|hk)(\d+)$/i);
  if (!match) return null;
  return { market: match[1].toUpperCase(), code: match[2] };
}

export default function ReportPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const { addHistoryItem } = useOutletContext<OutletContext>();
  const { state, startAnalysis, reset } = useAnalysis();
  const [windowYears, setWindowYears] = useState(DEFAULT_WINDOW_YEARS);
  const committedAnalysisKeyRef = useRef<string>("");
  const savedRef = useRef<string>("");

  const parsed = symbol ? parseSymbol(symbol) : null;

  // Reset window before analysis effect runs so the first fetch uses 10 years.
  useLayoutEffect(() => {
    if (!symbol) return;
    setWindowYears(DEFAULT_WINDOW_YEARS);
    try {
      localStorage.setItem(
        WINDOW_YEARS_STORAGE_KEY,
        String(DEFAULT_WINDOW_YEARS),
      );
    } catch {
      /* ignore */
    }
  }, [symbol]);

  useEffect(() => {
    if (!parsed) return;
    const key = `${parsed.code}:${windowYears}`;
    if (committedAnalysisKeyRef.current === key) {
      return;
    }
    committedAnalysisKeyRef.current = key;
    reset();
    startAnalysis(parsed.code, windowYears);
  }, [parsed?.code, windowYears, startAnalysis, reset]);

  useEffect(() => {
    if (
      state.stockName &&
      parsed &&
      symbol &&
      state.stockCode === parsed.code &&
      symbol !== savedRef.current
    ) {
      savedRef.current = symbol;
      addHistoryItem(symbol, parsed.code, state.stockName);
    }
  }, [state.stockName, state.stockCode, symbol, parsed?.code, addHistoryItem]);

  function handleSelect(stock: StockSearchResult) {
    const newSymbol = `${stock.market.toLowerCase()}${stock.code}`;
    navigate(`/analysis-report/${newSymbol}`);
  }

  if (!parsed) {
    return (
      <div className="text-center py-16 text-slate-500">
        无效的股票代码格式，请返回首页重新搜索。
      </div>
    );
  }

  function handleWindowYearsChange(next: number) {
    setWindowYears(next);
    try {
      localStorage.setItem(WINDOW_YEARS_STORAGE_KEY, String(next));
    } catch {
      /* ignore */
    }
  }

  return (
    <>
      <SearchBar onSelect={handleSelect} disabled={state.loading} />

      <div className="w-full max-w-4xl mx-auto mt-4 flex flex-wrap items-center gap-2 text-sm text-slate-600">
        <label htmlFor="window-years" className="shrink-0">
          历史数据窗口（年）
        </label>
        <select
          id="window-years"
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-slate-800 shadow-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-300 disabled:opacity-50"
          value={windowYears}
          disabled={state.loading}
          onChange={(e) =>
            handleWindowYearsChange(parseInt(e.target.value, 10))
          }
        >
          {WINDOW_YEAR_OPTIONS.map((y) => (
            <option key={y} value={y}>
              最近 {y} 年
            </option>
          ))}
        </select>
      </div>

      {state.error && !state.loading && Object.keys(state.steps).length === 0 && (
        <div className="max-w-xl mx-auto mt-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {state.error}
        </div>
      )}

      <AnalysisReport state={state} />
    </>
  );
}
