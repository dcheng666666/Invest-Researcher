import { useState, useEffect, useRef } from "react";
import { Search, X } from "lucide-react";
import { apiFetch } from "../lib/api";
import type { StockSearchResult } from "../types";

interface Props {
  onSelect: (stock: StockSearchResult) => void;
  disabled?: boolean;
}

export default function SearchBar({ onSelect, disabled }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);

  const [selected, setSelected] = useState(false);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (query.trim().length === 0 || selected) {
      setResults([]);
      setShowDropdown(false);
      setLoading(false);
      return;
    }

    const ac = new AbortController();
    setLoading(true);
    timerRef.current = setTimeout(async () => {
      try {
        const res = await apiFetch(
          `/api/search?q=${encodeURIComponent(query.trim())}`,
          { signal: ac.signal },
        );
        if (!res.ok) {
          setResults([]);
          setShowDropdown(true);
          return;
        }
        const data = (await res.json()) as { results?: StockSearchResult[] };
        setResults(Array.isArray(data.results) ? data.results : []);
        setShowDropdown(true);
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        setResults([]);
        setShowDropdown(true);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      ac.abort();
    };
  }, [query, selected]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative w-full max-w-xl mx-auto">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setSelected(false); }}
          onFocus={() => results.length > 0 && setShowDropdown(true)}
          placeholder="输入公司名或代码，如 贵州茅台、600519、腾讯控股、00700"
          disabled={disabled}
          className="w-full rounded-2xl border-2 border-slate-200 bg-white py-3.5 pl-12 pr-10 text-base
                     shadow-sm outline-none transition-all duration-200 focus:border-blue-500 focus:ring-4
                     focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50 sm:py-4 sm:text-lg"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setResults([]);
              setShowDropdown(false);
              setSelected(false);
            }}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {showDropdown && (
        <div className="absolute z-50 w-full mt-2 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden">
          {loading ? (
            <div className="px-4 py-3 text-slate-500">搜索中...</div>
          ) : results.length === 0 ? (
            <div className="px-4 py-3 text-slate-500">未找到匹配的股票</div>
          ) : (
            results.map((stock) => (
              <button
                key={`${stock.market}-${stock.code}`}
                onClick={() => {
                  onSelect(stock);
                  setQuery(`${stock.name} (${stock.code})`);
                  setSelected(true);
                  setShowDropdown(false);
                }}
                className="flex w-full flex-col items-start gap-1 px-4 py-3 text-left transition-colors hover:bg-blue-50 sm:flex-row sm:items-center sm:justify-between sm:gap-2"
              >
                <div className="min-w-0">
                  <span className="font-medium text-slate-900">{stock.name}</span>
                  <span className="mt-0.5 block text-sm text-slate-500 sm:ml-2 sm:mt-0 sm:inline">
                    {stock.code}
                  </span>
                </div>
                <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {stock.market}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
