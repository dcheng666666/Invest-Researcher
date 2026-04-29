import { useEffect, useRef } from "react";
import { useParams, useNavigate, useOutletContext } from "react-router-dom";
import { useAnalysis } from "../hooks/useAnalysis";
import AnalysisReport from "../components/AnalysisReport";
import SearchBar from "../components/SearchBar";
import type { StockSearchResult } from "../types";
import type { OutletContext } from "../App";

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
  const lastStartedRef = useRef<string>("");
  const savedRef = useRef<string>("");

  const parsed = symbol ? parseSymbol(symbol) : null;

  useEffect(() => {
    if (parsed && parsed.code !== lastStartedRef.current) {
      lastStartedRef.current = parsed.code;
      reset();
      startAnalysis(parsed.code);
    }
  }, [parsed?.code, startAnalysis, reset]);

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

  return (
    <>
      <SearchBar onSelect={handleSelect} disabled={state.loading} />

      {state.error && !state.loading && Object.keys(state.steps).length === 0 && (
        <div className="max-w-xl mx-auto mt-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {state.error}
        </div>
      )}

      <AnalysisReport state={state} />
    </>
  );
}
