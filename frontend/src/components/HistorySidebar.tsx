import { useNavigate, useParams } from "react-router-dom";
import { Clock, Trash2, X } from "lucide-react";
import type { HistoryItem } from "../types";

interface Props {
  items: HistoryItem[];
  removeItem: (symbol: string) => void;
  clearAll: () => void;
  className?: string;
  onClose?: () => void;
}

export default function HistorySidebar({
  items,
  removeItem,
  clearAll,
  className = "",
  onClose,
}: Props) {
  const navigate = useNavigate();
  const { symbol: activeSymbol } = useParams<{ symbol: string }>();

  return (
    <aside
      className={`flex h-full min-h-0 w-full flex-col border-r border-slate-200 bg-white/60 backdrop-blur-sm ${className}`.trim()}
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-4 py-4">
        <h3 className="flex min-w-0 items-center gap-2 text-sm font-semibold text-slate-700">
          <Clock className="h-4 w-4 shrink-0" />
          <span className="truncate">历史记录</span>
        </h3>
        <div className="flex shrink-0 items-center gap-1">
          {items.length > 0 && (
            <button
              type="button"
              onClick={clearAll}
              className="flex min-h-10 min-w-10 items-center justify-center rounded-lg p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500 md:min-h-0 md:min-w-0 md:p-1"
              title="清空全部"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="flex min-h-10 min-w-10 items-center justify-center rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 md:hidden"
              aria-label="关闭历史记录"
            >
              <X className="h-5 w-5" aria-hidden />
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {items.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-slate-400">
            暂无分析记录
          </p>
        ) : (
          <ul className="py-1">
            {items.map((item) => {
              const isActive = activeSymbol === item.symbol;
              return (
                <li key={item.symbol} className="group relative">
                  <button
                    type="button"
                    onClick={() => navigate(`/analysis-report/${item.symbol}`)}
                    className={`flex min-h-[44px] w-full flex-col justify-center px-4 py-3 text-left transition-colors md:min-h-0 md:py-2.5 md:pr-9 pr-12 ${
                      isActive
                        ? "border-r-2 border-blue-500 bg-blue-50"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <div
                      className={`truncate text-sm font-medium ${isActive ? "text-blue-700" : "text-slate-800"}`}
                    >
                      {item.name}
                    </div>
                    <div className="text-xs text-slate-400">{item.code}</div>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeItem(item.symbol);
                    }}
                    className="absolute right-2 top-1/2 flex min-h-10 min-w-10 -translate-y-1/2 items-center justify-center rounded-lg p-2 text-slate-400 transition-all hover:bg-red-50 hover:text-red-500 md:min-h-0 md:min-w-0 md:p-1 md:opacity-0 md:group-hover:opacity-100 opacity-100"
                    aria-label={`删除 ${item.name}`}
                  >
                    <X className="h-4 w-4 md:h-3.5 md:w-3.5" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
