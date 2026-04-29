import { useNavigate, useParams } from "react-router-dom";
import { Clock, Trash2, X } from "lucide-react";
import type { HistoryItem } from "../types";

interface Props {
  items: HistoryItem[];
  removeItem: (symbol: string) => void;
  clearAll: () => void;
}

export default function HistorySidebar({ items, removeItem, clearAll }: Props) {
  const navigate = useNavigate();
  const { symbol: activeSymbol } = useParams<{ symbol: string }>();

  return (
    <aside className="w-64 shrink-0 border-r border-slate-200 bg-white/60 backdrop-blur-sm overflow-y-auto">
      <div className="px-4 py-4 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <Clock className="w-4 h-4" />
          历史记录
        </h3>
        {items.length > 0 && (
          <button
            onClick={clearAll}
            className="p-1 rounded text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
            title="清空全部"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="px-4 py-6 text-xs text-slate-400 text-center">
          暂无分析记录
        </p>
      ) : (
        <ul className="py-1">
          {items.map((item) => {
            const isActive = activeSymbol === item.symbol;
            return (
              <li key={item.symbol} className="group relative">
                <button
                  onClick={() => navigate(`/analysis-report/${item.symbol}`)}
                  className={`w-full text-left px-4 py-2.5 pr-9 transition-colors ${
                    isActive
                      ? "bg-blue-50 border-r-2 border-blue-500"
                      : "hover:bg-slate-50"
                  }`}
                >
                  <div className={`text-sm font-medium truncate ${isActive ? "text-blue-700" : "text-slate-800"}`}>
                    {item.name}
                  </div>
                  <div className="text-xs text-slate-400">{item.code}</div>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeItem(item.symbol);
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded
                             text-slate-300 hover:text-red-500 hover:bg-red-50
                             opacity-0 group-hover:opacity-100 transition-all"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
