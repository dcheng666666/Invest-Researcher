import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

type VerdictOpt =
  | "excellent"
  | "good"
  | "neutral"
  | "warning"
  | "danger"
  | "";

interface ValuationScreenRow {
  refresh_date: string;
  market: string;
  code: string;
  name: string;
  board: string;
  overall_score: number | null;
  overall_verdict: string | null;
  step_scores: number[] | null;
  valuation_score: number | null;
  valuation_verdict: string | null;
  pe_percentile: number | null;
  peg: number | null;
  current_pe: number | null;
  step_errors: Record<string, string>;
  error: string | null;
}

/** Table column order matches backend ``STEP_CONFIGS`` (step 1..5). */
const STEP_SCORE_LABELS = [
  "业绩长跑",
  "血液检查",
  "厚道程度",
  "生意逻辑",
  "估值称重",
] as const;

const OVERALL_VERDICT_ZH: Record<string, string> = {
  excellent: "优秀",
  good: "良好",
  neutral: "一般",
  warning: "警惕",
  danger: "危险",
};

function formatOverallVerdict(v: string | null | undefined): string {
  if (!v) return "—";
  return OVERALL_VERDICT_ZH[v] ?? v;
}

function stepScoreAt(
  scores: number[] | null | undefined,
  index: number,
): string {
  if (!scores || index >= scores.length) return "—";
  return String(scores[index]);
}

interface ListResponse {
  refresh_date: string | null;
  total: number;
  items: ValuationScreenRow[];
  completed_refresh_dates: string[];
}

interface MetaResponse {
  latest_completed_refresh_date: string | null;
  completed_refresh_dates: string[];
}

type SortDir = "asc" | "desc";

function parseSortTokens(sort: string): string[] {
  return sort
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

function joinSortTokens(tokens: string[]): string {
  return tokens.length > 0 ? tokens.join(",") : "overall_desc";
}

function overallSortDir(sort: string): SortDir | null {
  const t = parseSortTokens(sort).find((x) => x.startsWith("overall_"));
  if (t === "overall_desc") return "desc";
  if (t === "overall_asc") return "asc";
  return null;
}

function stepSortDir(sort: string, stepIndex: number): SortDir | null {
  const prefix = `step${stepIndex + 1}_`;
  const t = parseSortTokens(sort).find((x) => x.startsWith(prefix));
  if (t?.endsWith("_desc")) return "desc";
  if (t?.endsWith("_asc")) return "asc";
  return null;
}

function SortableTh({
  label,
  activeDir,
  onClick,
}: {
  label: ReactNode;
  activeDir: SortDir | null;
  onClick: () => void;
}) {
  return (
    <th
      scope="col"
      className="px-3 py-2 align-bottom whitespace-nowrap text-slate-600"
    >
      <button
        type="button"
        className="group inline-flex w-full max-w-full items-center gap-1 rounded-md px-1 py-0.5 text-left font-medium text-slate-700 hover:bg-slate-200/80 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
        onClick={onClick}
      >
        <span className="min-w-0 flex-1">{label}</span>
        <span className="shrink-0 text-xs tabular-nums text-slate-400 group-hover:text-slate-600">
          {activeDir === null ? "↕" : activeDir === "desc" ? "↓" : "↑"}
        </span>
      </button>
    </th>
  );
}

function boardLabel(board: string): string {
  if (board === "STAR") return "科创板";
  if (board === "CHINEXT") return "创业板";
  return board;
}

export default function ValuationScreenPage() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /** Empty: use API default (latest completed refresh_date). */
  const [refreshDate, setRefreshDate] = useState("");
  const [board, setBoard] = useState("all");
  const [overallVerdict, setOverallVerdict] = useState<VerdictOpt>("");
  const [stepMin, setStepMin] = useState<string[]>(["", "", "", "", ""]);
  const [stepMax, setStepMax] = useState<string[]>(["", "", "", "", ""]);
  const [sort, setSort] = useState<string>("overall_desc");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const stepBoundsKey = `${stepMin.join(",")}|${stepMax.join(",")}`;

  const toggleOverallSort = useCallback(() => {
    setOffset(0);
    setSort((prev) => {
      const tokens = parseSortTokens(prev);
      const idx = tokens.findIndex((t) => t.startsWith("overall_"));
      if (idx >= 0) {
        const cur = tokens[idx];
        const next =
          cur === "overall_desc" ? "overall_asc" : "overall_desc";
        const copy = [...tokens];
        copy[idx] = next;
        return joinSortTokens(copy);
      }
      return joinSortTokens([...tokens, "overall_desc"]);
    });
  }, []);

  const toggleStepSort = useCallback((stepIndex: number) => {
    setOffset(0);
    const n = stepIndex + 1;
    const prefix = `step${n}_`;
    const desc = `${prefix}desc`;
    const asc = `${prefix}asc`;
    setSort((prev) => {
      const tokens = parseSortTokens(prev);
      const idx = tokens.findIndex((t) => t.startsWith(prefix));
      if (idx >= 0) {
        const cur = tokens[idx];
        const next = cur === desc ? asc : desc;
        const copy = [...tokens];
        copy[idx] = next;
        return joinSortTokens(copy);
      }
      return joinSortTokens([...tokens, desc]);
    });
  }, []);

  const loadMeta = useCallback(async () => {
    const res = await fetch("/api/valuation-screen/meta");
    if (!res.ok) throw new Error(`meta ${res.status}`);
    const j = (await res.json()) as MetaResponse;
    setMeta(j);
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      const rd = refreshDate.trim();
      if (rd) {
        params.set("refresh_date", rd);
      }
      if (board && board !== "all") params.set("board", board);
      if (overallVerdict) params.set("overall_verdict", overallVerdict);
      for (let i = 0; i < 5; i++) {
        const lo = stepMin[i]?.trim() ?? "";
        const hi = stepMax[i]?.trim() ?? "";
        const n = i + 1;
        if (lo !== "") params.set(`min_step${n}`, lo);
        if (hi !== "") params.set(`max_step${n}`, hi);
      }
      params.set("sort", sort);
      params.set("limit", String(limit));
      params.set("offset", String(offset));

      const res = await fetch(`/api/valuation-screen?${params.toString()}`);
      if (!res.ok) throw new Error(`list ${res.status}`);
      const j = (await res.json()) as ListResponse;
      setData(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [refreshDate, board, overallVerdict, stepBoundsKey, sort, offset]);

  useEffect(() => {
    void loadMeta().catch((e) => setError(String(e)));
  }, [loadMeta]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const dateOptions = data?.completed_refresh_dates?.length
    ? data.completed_refresh_dates
    : meta?.completed_refresh_dates ?? [];

  const hasActiveValuationFilters =
    refreshDate.trim() !== "" ||
    board !== "all" ||
    overallVerdict !== "" ||
    stepMin.some((s) => s.trim() !== "") ||
    stepMax.some((s) => s.trim() !== "");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">估值筛选报表</h2>
          <p className="text-sm text-slate-500 mt-1">
            数据来自批量脚本写入的 SQLite；默认展示最近已完成的一轮自然日 refresh。
          </p>
        </div>
        <Link
          to="/"
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          返回首页
        </Link>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            数据日期
            <select
              className="border border-slate-200 rounded-lg px-2 py-2 text-sm text-slate-900"
              value={refreshDate}
              onChange={(e) => {
                setRefreshDate(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">最近已完成</option>
              {dateOptions.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            板块
            <select
              className="border border-slate-200 rounded-lg px-2 py-2 text-sm"
              value={board}
              onChange={(e) => {
                setBoard(e.target.value);
                setOffset(0);
              }}
            >
              <option value="all">全部</option>
              <option value="STAR">科创板</option>
              <option value="CHINEXT">创业板</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            综合 verdict
            <select
              className="border border-slate-200 rounded-lg px-2 py-2 text-sm"
              value={overallVerdict}
              onChange={(e) => {
                setOverallVerdict(e.target.value as VerdictOpt);
                setOffset(0);
              }}
            >
              <option value="">不限</option>
              <option value="excellent">优秀 (excellent)</option>
              <option value="good">良好 (good)</option>
              <option value="neutral">一般 (neutral)</option>
              <option value="warning">警惕 (warning)</option>
              <option value="danger">危险 (danger)</option>
            </select>
          </label>
        </div>

        <div className="border-t border-slate-100 pt-4 space-y-3">
          <p className="text-xs font-medium text-slate-700">
            子维度分值区间（1–5，对应表头五列；可只填最小或最大）
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {STEP_SCORE_LABELS.map((label, idx) => (
              <label
                key={label}
                className="flex flex-col gap-1 text-xs text-slate-600"
              >
                <span className="text-slate-800 font-medium">{label}</span>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    min={0}
                    max={5}
                    placeholder="min"
                    className="w-full border border-slate-200 rounded-lg px-2 py-2 text-sm"
                    value={stepMin[idx]}
                    onChange={(e) => {
                      setStepMin((prev) => {
                        const next = [...prev];
                        next[idx] = e.target.value;
                        return next;
                      });
                      setOffset(0);
                    }}
                  />
                  <span className="text-slate-400 shrink-0">—</span>
                  <input
                    type="number"
                    min={0}
                    max={5}
                    placeholder="max"
                    className="w-full border border-slate-200 rounded-lg px-2 py-2 text-sm"
                    value={stepMax[idx]}
                    onChange={(e) => {
                      setStepMax((prev) => {
                        const next = [...prev];
                        next[idx] = e.target.value;
                        return next;
                      });
                      setOffset(0);
                    }}
                  />
                </div>
              </label>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {loading && !data && (
        <p className="text-slate-500 text-sm">加载中…</p>
      )}

      {data && (
        <>
          <p className="text-sm text-slate-600">
            当前数据日{" "}
            <span className="font-mono font-medium">
              {data.refresh_date ?? "—"}
            </span>
            ，共 <span className="font-medium">{data.total}</span> 条
          </p>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600 text-left">
                <tr>
                  <th className="px-3 py-2 font-medium whitespace-nowrap">板块</th>
                  <th className="px-3 py-2 font-medium whitespace-nowrap">代码</th>
                  <th className="px-3 py-2 font-medium whitespace-nowrap">名称</th>
                  <SortableTh
                    label="综合 verdict"
                    activeDir={overallSortDir(sort)}
                    onClick={toggleOverallSort}
                  />
                  <SortableTh
                    label="综合分"
                    activeDir={overallSortDir(sort)}
                    onClick={toggleOverallSort}
                  />
                  {STEP_SCORE_LABELS.map((label, idx) => (
                    <SortableTh
                      key={label}
                      label={label}
                      activeDir={stepSortDir(sort, idx)}
                      onClick={() => toggleStepSort(idx)}
                    />
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td
                      colSpan={10}
                      className="px-3 py-8 text-center text-slate-500"
                    >
                      {hasActiveValuationFilters ? (
                        "无数据。"
                      ) : (
                        <>
                          无数据。请先运行{" "}
                          <code className="text-xs bg-slate-100 px-1 rounded">
                            uv run python scripts/scan_board_valuation.py
                          </code>
                        </>
                      )}
                    </td>
                  </tr>
                ) : (
                  data.items.map((row) => {
                    const sym = `${row.market.toLowerCase()}${row.code}`;
                    return (
                      <tr
                        key={`${row.market}-${row.code}`}
                        className="border-t border-slate-100 hover:bg-slate-50/80"
                      >
                        <td className="px-3 py-2">{boardLabel(row.board)}</td>
                        <td className="px-3 py-2 font-mono">
                          <Link
                            to={`/analysis-report/${sym}`}
                            className="text-blue-600 hover:text-blue-800 font-medium hover:underline"
                          >
                            {row.code}
                          </Link>
                        </td>
                        <td className="px-3 py-2 max-w-[200px] truncate">
                          {row.name}
                        </td>
                        <td className="px-3 py-2 text-xs whitespace-nowrap">
                          {formatOverallVerdict(row.overall_verdict)}
                        </td>
                        <td className="px-3 py-2 tabular-nums">
                          {row.overall_score ?? "—"}
                        </td>
                        {STEP_SCORE_LABELS.map((label, idx) => (
                          <td
                            key={label}
                            className="px-3 py-2 tabular-nums text-center"
                          >
                            {stepScoreAt(row.step_scores, idx)}
                          </td>
                        ))}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          {data.total > limit && (
            <div className="flex gap-3 items-center text-sm">
              <button
                type="button"
                className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white disabled:opacity-40"
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - limit))}
              >
                上一页
              </button>
              <button
                type="button"
                className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white disabled:opacity-40"
                disabled={offset + limit >= data.total}
                onClick={() => setOffset((o) => o + limit)}
              >
                下一页
              </button>
              <span className="text-slate-500">
                {offset + 1}–{Math.min(offset + limit, data.total)} / {data.total}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
