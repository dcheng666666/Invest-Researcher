import { useState } from "react";

export interface QualityHeatTile {
  name: string;
  label: string;
  status: "pass" | "warn" | "fail" | "n/a";
  detail: string;
}

const STATUS_STYLES: Record<QualityHeatTile["status"], string> = {
  pass: "bg-emerald-500 text-white border-emerald-600 shadow-sm",
  warn: "bg-amber-400 text-amber-950 border-amber-500 shadow-sm",
  fail: "bg-red-500 text-white border-red-600 shadow-sm",
  "n/a": "bg-slate-200 text-slate-600 border-slate-300",
};

interface Props {
  tiles: QualityHeatTile[];
}

export default function QualitySignalHeatmap({ tiles }: Props) {
  const [active, setActive] = useState<QualityHeatTile | null>(null);

  if (!tiles.length) return null;

  return (
    <div className="mt-4" onMouseLeave={() => setActive(null)}>
      <h4 className="text-sm font-medium text-slate-600 mb-2">质量指标热力图</h4>
      <p className="text-xs text-slate-400 mb-2">
        六项核心信号（长期 ROE、ROA、FCF、利润现金兑现、OCF、杠杆）；悬停或按 Tab
        聚焦格子查看依据。
      </p>
      <div
        className="mb-2 min-h-[2.75rem] rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700"
        aria-live="polite"
      >
        {active ? (
          <>
            <span className="font-semibold text-slate-800">{active.label}</span>
            {active.detail ? (
              <span className="text-slate-600">：{active.detail}</span>
            ) : null}
          </>
        ) : (
          <span className="text-slate-400">
            将指针移到彩色格子上，或按 Tab 选中后查看判定说明。
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
        {tiles.map((t) => (
          <button
            key={t.name}
            type="button"
            aria-label={`${t.label}，${t.detail || "无说明"}`}
            onMouseEnter={() => setActive(t)}
            onFocus={() => setActive(t)}
            onBlur={(e) => {
              const next = e.relatedTarget as Node | null;
              if (next && e.currentTarget.parentElement?.contains(next)) return;
              setActive(null);
            }}
            className={`rounded-lg border px-2 py-2.5 text-center text-xs font-medium leading-tight outline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-400 cursor-help ${STATUS_STYLES[t.status]}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block size-2 rounded-sm bg-emerald-500" /> 达标
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block size-2 rounded-sm bg-amber-400" /> 警示
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block size-2 rounded-sm bg-red-500" /> 未达标
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block size-2 rounded-sm bg-slate-300" /> 无数据
        </span>
      </div>
    </div>
  );
}
