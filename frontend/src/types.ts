export interface StockSearchResult {
  code: string;
  name: string;
  market: string;
}

export interface PeriodMetric {
  period: string;
  value: number;
  /** Cash dividend distribution count for this period (payout step bars). */
  distribution_count?: number;
}

/** Step 2 chart reference: industry medians from local DB (display-only). */
export interface IndustryBenchmarkRef {
  industry_key: string;
  as_of: string;
  roe_median: number | null;
  roa_median: number | null;
  gross_margin_median: number | null;
  debt_ratio_median: number | null;
}

export interface AnnualRevenueChartPoint {
  period: string;
  value: number;
  is_partial?: boolean;
  partial_through?: string | null;
}

export type Verdict = "excellent" | "good" | "neutral" | "warning" | "danger";

export interface StepData {
  verdict: Verdict;
  verdict_reason: string;
  score: number;
  [key: string]: unknown;
}

export interface StepEvent {
  step: number;
  title: string;
  status: "running" | "completed" | "error";
  data?: StepData;
  error?: string;
}

export interface CompleteEvent {
  overall_score: number;
  scores: number[];
  stock_name: string;
  stock_code: string;
  /** Display name of 行业 from security profile; null if upstream omitted it. */
  industry: string | null;
}

export interface AnalysisState {
  stockName: string;
  stockCode: string;
  /** Same as ``CompleteEvent.industry`` once step 0 completes. */
  industry: string | null;
  steps: Record<number, StepEvent>;
  complete: CompleteEvent | null;
  loading: boolean;
  error: string | null;
}

export interface HistoryItem {
  symbol: string;
  code: string;
  name: string;
  lastVisited: string;
}
