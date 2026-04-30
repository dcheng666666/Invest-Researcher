import {
  TrendingUp,
  Heart,
  Shield,
  Activity,
  Scale,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import type {
  AnnualRevenueChartPoint,
  IndustryBenchmarkRef,
  PeriodMetric,
  StepEvent,
  Verdict,
} from "../types";
import {
  MetricLineChart,
  MetricBarChart,
  DualBarChart,
  RevenueMarketCapChart,
} from "./FinancialChart";
import QualitySignalHeatmap, {
  type QualityHeatTile,
} from "./QualitySignalHeatmap";

const STEP_META: Record<
  number,
  { icon: typeof TrendingUp; label: string; subtitle: string }
> = {
  1: {
    icon: TrendingUp,
    label: "业绩长跑",
    subtitle: '判断是不是一门"好生意"',
  },
  2: {
    icon: Activity,
    label: "血液检查",
    subtitle: '判断经营质量"健不健康"',
  },
  3: { icon: Heart, label: "厚道程度", subtitle: '判断管理层对股东"好不好"' },
  4: { icon: Shield, label: "生意逻辑", subtitle: '判断护城河"深不深"（参考项，不计入综合评分）' },
  5: { icon: Scale, label: "估值称重", subtitle: '判断现在的价格"贵不贵"' },
};

const VERDICT_STYLES: Record<
  Verdict,
  { bg: string; text: string; label: string }
> = {
  excellent: { bg: "bg-emerald-50", text: "text-emerald-700", label: "优秀" },
  good: { bg: "bg-lime-50", text: "text-lime-700", label: "良好" },
  neutral: { bg: "bg-amber-50", text: "text-amber-700", label: "一般" },
  warning: { bg: "bg-orange-50", text: "text-orange-700", label: "警惕" },
  danger: { bg: "bg-red-50", text: "text-red-700", label: "危险" },
};

function ScoreBadge({ score }: { score: number }) {
  const colors =
    score >= 4
      ? "bg-emerald-100 text-emerald-800"
      : score >= 3
        ? "bg-amber-100 text-amber-800"
        : "bg-red-100 text-red-800";
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-sm font-bold ${colors}`}>
      {score}/5
    </span>
  );
}

const pctFormatter = (v: number) => `${(v * 100).toFixed(1)}%`;
const yiFormatter = (v: number) => `${v.toFixed(0)}亿`;

function StepCharts({ step, data }: { step: number; data: Record<string, unknown> }) {
  switch (step) {
    case 1: {
      const ttmRevenue = (data.ttm_revenue_chart as AnnualRevenueChartPoint[]) || [];
      const ttmProfit = (data.ttm_profit_chart as AnnualRevenueChartPoint[]) || [];
      const sqRevenue = (data.single_quarter_revenue as PeriodMetric[]) || [];
      const sqProfit = (data.single_quarter_profit as PeriodMetric[]) || [];
      const revGrowth = (data.revenue_growth_rates as PeriodMetric[]) || [];
      const profitGrowth = (data.profit_growth_rates as PeriodMetric[]) || [];

      const periodSet = new Set<string>();
      const addPeriod = (p: string) => { if (p) periodSet.add(p); };
      for (const arr of [sqRevenue, sqProfit, revGrowth, profitGrowth]) {
        arr.forEach((d: PeriodMetric) => addPeriod(d.period));
      }
      ttmRevenue.forEach((p) => addPeriod(p.period));
      ttmProfit.forEach((p) => addPeriod(p.period));
      const sharedPeriods = Array.from(periodSet).sort();

      return (
        <>
          <DualBarChart
            title="TTM 营收与扣非净利润"
            series={[
              { data: ttmRevenue as PeriodMetric[], name: "TTM营收", color: "#3b82f6" },
              { data: ttmProfit as PeriodMetric[], name: "TTM扣非净利润", color: "#10b981" },
            ]}
            yAxisFormatter={yiFormatter}
            sharedPeriods={sharedPeriods}
            rightMargin={70}
          />
          <p className="text-xs text-slate-400 mt-1">
            TTM = 过去 12 个月滚动累计，平滑季节性波动后的长期业绩趋势。
          </p>
          <DualBarChart
            title="单季营收与扣非净利润"
            series={[
              { data: sqRevenue, name: "营业收入", color: "#3b82f6" },
              { data: sqProfit, name: "扣非净利润", color: "#10b981" },
            ]}
            yAxisFormatter={yiFormatter}
            sharedPeriods={sharedPeriods}
            rightMargin={70}
          />
          <MetricLineChart
            title="同比增长率"
            series={[
              { data: revGrowth, name: "营收增长率", color: "#3b82f6" },
              { data: profitGrowth, name: "利润增长率", color: "#10b981" },
            ]}
            yAxisFormatter={pctFormatter}
            referenceLine={{ y: 0, label: "" }}
            sharedPeriods={sharedPeriods}
            rightMargin={70}
            autoClampY
          />
          <p className="text-xs text-slate-400 mt-1">
            同比增长率为报告期累计同比（Q1/H1/Q3/年报为相应期累计），非单季度、亦非 TTM。
          </p>
        </>
      );
    }
    case 2: {
      const roeSeries = (data.roe as PeriodMetric[]) || [];
      const fcfSeries = (data.free_cash_flow as PeriodMetric[]) || [];
      const fcfTtmSeries = (data.free_cash_flow_ttm as PeriodMetric[]) || [];
      const debtSeries = (data.debt_ratio as PeriodMetric[]) || [];
      const bench = data.industry_benchmark as IndustryBenchmarkRef | null | undefined;
      const periodSet = new Set<string>();
      roeSeries.forEach((d) => periodSet.add(d.period));
      fcfSeries.forEach((d) => periodSet.add(d.period));
      fcfTtmSeries.forEach((d) => periodSet.add(d.period));
      debtSeries.forEach((d) => periodSet.add(d.period));
      const sharedPeriods = Array.from(periodSet).sort();

      const roeRefLines: {
        y: number;
        label: string;
        color?: string;
        strokeDasharray?: string;
      }[] = [
        { y: 0.15, label: "ROE 15%", color: "#94a3b8", strokeDasharray: "5 5" },
      ];
      if (bench?.roe_median != null && Number.isFinite(bench.roe_median)) {
        roeRefLines.push({
          y: bench.roe_median,
          label: `行业中位数 ${(bench.roe_median * 100).toFixed(1)}%（${bench.industry_key}，截至 ${bench.as_of}）`,
          color: "#f97316",
          strokeDasharray: "4 4",
        });
      }

      const debtRefLines: {
        y: number;
        label: string;
        color?: string;
        strokeDasharray?: string;
      }[] = [];
      if (bench?.debt_ratio_median != null && Number.isFinite(bench.debt_ratio_median)) {
        debtRefLines.push({
          y: bench.debt_ratio_median,
          label: `行业中位数 ${(bench.debt_ratio_median * 100).toFixed(1)}%（${bench.industry_key}，截至 ${bench.as_of}）`,
          color: "#f97316",
          strokeDasharray: "4 4",
        });
      }

      return (
        <>
          <QualitySignalHeatmap
            tiles={(data.quality_heatmap as QualityHeatTile[]) ?? []}
          />
          <MetricLineChart
            title="ROE"
            series={[{ data: roeSeries, name: "ROE", color: "#3b82f6" }]}
            yAxisFormatter={pctFormatter}
            referenceLines={roeRefLines}
            sharedPeriods={sharedPeriods}
          />
          <p className="text-xs text-slate-400 mt-1">
            灰色虚线：ROE 15% 经验参考
            {roeRefLines.length > 1
              ? "；橙色虚线：本地库行业 ROE 中位数示意（不参与评分）。"
              : "。"}
            {bench == null ? " 当前股票行业在基准库中无匹配行。" : ""}
          </p>
          <DualBarChart
            title="自由现金流（亿元）"
            series={[
              { data: fcfSeries, name: "单季", color: "#10b981" },
              { data: fcfTtmSeries, name: "TTM", color: "#3b82f6" },
            ]}
            yAxisFormatter={yiFormatter}
            sharedPeriods={sharedPeriods}
            rightMargin={70}
          />
          <p className="text-xs text-slate-400 mt-1">
            TTM = 以该报告期为终点，向前连续四个单季自由现金流之和。
          </p>
          <MetricLineChart
            title="资产负债率"
            series={[
              { data: debtSeries, name: "资产负债率", color: "#8b5cf6" },
            ]}
            yAxisFormatter={pctFormatter}
            referenceLines={debtRefLines}
            sharedPeriods={sharedPeriods}
          />
          {debtRefLines.length > 0 ? (
            <p className="text-xs text-slate-400 mt-1">
              橙色虚线：本地库行业资产负债率中位数示意（不参与评分）。
            </p>
          ) : null}
        </>
      );
    }
    case 3:
      return (
        <>
          <MetricBarChart
            title="分红支付率"
            data={(data.payout_ratios as PeriodMetric[]) || []}
            name="分红支付率"
            color="#3b82f6"
            yAxisFormatter={pctFormatter}
          />
          <p className="text-xs text-slate-400 mt-1">
            分红支付率 = 每股分红 ÷ 每股扣非收益（口径与扣非净利润一致，规避送转股造成的失真）。分红按财务年度汇总：8 月及之前公告的归属上一财年，之后归属当年；仅展示利润为正的年份。
          </p>
        </>
      );
    case 4:
      return (
        <MetricLineChart
          title="利润率趋势"
          series={[
            { data: (data.gross_margins as PeriodMetric[]) || [], name: "毛利率", color: "#f59e0b" },
            { data: (data.net_margins as PeriodMetric[]) || [], name: "净利率", color: "#8b5cf6" },
          ]}
          yAxisFormatter={pctFormatter}
        />
      );
    case 5: {
      const peMean = data.pe_mean as number | undefined;
      const peLow = data.pe_low as number | undefined;
      const peHigh = data.pe_high as number | undefined;
      const refLines: { y: number; label: string; color: string; strokeDasharray?: string }[] = [];
      if (peLow != null) refLines.push({ y: peLow, label: `低估 -1σ ${peLow.toFixed(1)}`, color: "#10b981" });
      if (peMean != null) refLines.push({ y: peMean, label: `均值 ${peMean.toFixed(1)}`, color: "#6366f1" });
      if (peHigh != null) refLines.push({ y: peHigh, label: `高估 +1σ ${peHigh.toFixed(1)}`, color: "#ef4444" });

      const peHistory = (data.pe_history as PeriodMetric[]) || [];
      const ttmRevenue = (data.ttm_revenue_chart as AnnualRevenueChartPoint[]) || [];
      const ttmProfit = (data.ttm_profit_chart as AnnualRevenueChartPoint[]) || [];
      const mcapMonthly = (data.market_cap_monthly as PeriodMetric[]) || [];

      // Build a shared monthly X-axis covering both charts so year ticks line
      // up vertically. Quarterly TTM points are projected to their quarter-end
      // month; the start is rounded down to January of the earliest year so
      // the first year tick is always present.
      const quarterToEndMonth = (q: string): string => {
        const [y, qN] = q.split("Q");
        const m = parseInt(qN, 10) * 3;
        return `${y}-${m.toString().padStart(2, "0")}`;
      };
      const monthSamples: string[] = [];
      peHistory.forEach((p) => monthSamples.push(p.period));
      mcapMonthly.forEach((p) => monthSamples.push(p.period));
      ttmRevenue.forEach((p) => monthSamples.push(quarterToEndMonth(p.period)));
      ttmProfit.forEach((p) => monthSamples.push(quarterToEndMonth(p.period)));

      let sharedMonthlyPeriods: string[] | undefined;
      if (monthSamples.length > 0) {
        monthSamples.sort();
        const startYear = parseInt(monthSamples[0].slice(0, 4), 10);
        const last = monthSamples[monthSamples.length - 1];
        const endYear = parseInt(last.slice(0, 4), 10);
        const endMonth = parseInt(last.slice(5, 7), 10);
        const periods: string[] = [];
        let y = startYear;
        let m = 1;
        while (y < endYear || (y === endYear && m <= endMonth)) {
          periods.push(`${y}-${m.toString().padStart(2, "0")}`);
          m += 1;
          if (m > 12) {
            m = 1;
            y += 1;
          }
        }
        sharedMonthlyPeriods = periods;
      }

      return (
        <>
          <MetricLineChart
            title="PE-TTM 月度走势"
            series={[
              { data: peHistory, name: "PE-TTM", color: "#f97316" },
            ]}
            referenceLines={refLines}
            sharedPeriods={sharedMonthlyPeriods}
            rightMargin={75}
          />
          <RevenueMarketCapChart
            title="市值与业绩对照"
            ttmRevenueChart={ttmRevenue}
            ttmProfitChart={ttmProfit}
            marketCapMonthly={mcapMonthly}
            marketCapLabel="总市值（月度）"
            caption="柱状图为各季度的TTM（过去12个月滚动）营收与扣非净利润，柱体定位在该季度末月；折线为月度市值。业绩持续上行而市值停滞 → 估值偏低；反之则偏高。"
            sharedPeriods={sharedMonthlyPeriods}
          />
        </>
      );
    }
    default:
      return null;
  }
}

interface Props {
  stepNum: number;
  event?: StepEvent;
}

export default function StepCard({ stepNum, event }: Props) {
  const meta = STEP_META[stepNum];
  if (!meta) return null;

  const Icon = meta.icon;
  const isRunning = event?.status === "running";
  const isCompleted = event?.status === "completed";
  const isError = event?.status === "error";
  const data = event?.data;
  const verdict = data?.verdict as Verdict | undefined;
  const verdictStyle = verdict ? VERDICT_STYLES[verdict] : null;

  return (
    <div
      className={`bg-white rounded-2xl border transition-all duration-300 overflow-hidden
        ${isRunning ? "border-blue-300 shadow-md shadow-blue-100" : ""}
        ${isCompleted ? "border-slate-200 shadow-sm" : ""}
        ${isError ? "border-red-300 shadow-sm" : ""}
        ${!event ? "border-slate-100 opacity-60" : ""}
      `}
    >
      <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6">
        <div className="flex min-w-0 items-start gap-3">
          <div
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl
          ${isCompleted ? (verdictStyle?.bg || "bg-slate-100") : "bg-slate-100"}
        `}
          >
            <Icon
              className={`w-5 h-5 ${isCompleted ? (verdictStyle?.text || "text-slate-600") : "text-slate-500"}`}
            />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-slate-400">
                步骤 {stepNum}
              </span>
              {isRunning && (
                <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              )}
              {isCompleted && (
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              )}
              {isError && <AlertCircle className="h-4 w-4 text-red-500" />}
            </div>
            <h3 className="font-semibold text-slate-900">{meta.label}</h3>
            <p className="text-sm text-slate-500">{meta.subtitle}</p>
          </div>
        </div>
        {isCompleted && data && (
          <div className="shrink-0 self-start sm:self-center">
            <ScoreBadge score={data.score as number} />
          </div>
        )}
      </div>

      {isRunning && (
        <div className="flex items-center justify-center px-4 py-8 sm:px-6">
          <div className="flex items-center gap-3 text-blue-600">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">正在分析...</span>
          </div>
        </div>
      )}

      {isError && (
        <div className="bg-red-50 px-4 py-4 sm:px-6">
          <p className="text-sm text-red-600">{event?.error || "分析出错"}</p>
        </div>
      )}

      {isCompleted && data && (
        <div className="px-4 py-4 sm:px-6">
          {verdictStyle && (
            <div
              className={`inline-flex items-center px-3 py-1 rounded-lg text-sm font-medium ${verdictStyle.bg} ${verdictStyle.text} mb-3`}
            >
              {verdictStyle.label}
            </div>
          )}
          <p className="text-sm text-slate-700 leading-relaxed">
            {data.verdict_reason as string}
          </p>

          {Boolean((data as Record<string, unknown>).llm_analysis) && (
            <div className="mt-4 p-4 bg-slate-50 rounded-xl">
              <h4 className="text-sm font-medium text-slate-600 mb-2">
                AI 深度分析
              </h4>
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                {((data as Record<string, unknown>).llm_analysis as string).startsWith("LLM分析暂时不可用")
                  ? "AI 分析功能需要配置 LLM API 密钥。请在 .env 文件中设置 OPENAI_API_KEY 或其他 LLM 提供商的密钥。"
                  : (data as Record<string, unknown>).llm_analysis as string}
              </p>
            </div>
          )}

          <StepCharts step={stepNum} data={data as Record<string, unknown>} />

          {stepNum === 1 && data.revenue_cagr != null && (
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="bg-blue-50 rounded-xl p-3 text-center">
                <div className="text-xs text-blue-600">营收 CAGR</div>
                <div className="text-lg font-bold text-blue-800">
                  {((data.revenue_cagr as number) * 100).toFixed(1)}%
                </div>
              </div>
              <div className="bg-emerald-50 rounded-xl p-3 text-center">
                <div className="text-xs text-emerald-600">利润 CAGR</div>
                <div className="text-lg font-bold text-emerald-800">
                  {data.profit_cagr != null
                    ? `${((data.profit_cagr as number) * 100).toFixed(1)}%`
                    : "N/A"}
                </div>
              </div>
            </div>
          )}

          {stepNum === 2 && data.avg_roe != null && (
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="bg-blue-50 rounded-xl p-3 text-center">
                <div className="text-xs text-blue-600">年均 ROE</div>
                <div className="text-lg font-bold text-blue-800">
                  {((data.avg_roe as number) * 100).toFixed(1)}%
                </div>
              </div>
              <div className="bg-emerald-50 rounded-xl p-3 text-center">
                <div className="text-xs text-emerald-600">FCF 为正季度</div>
                <div className="text-lg font-bold text-emerald-800">
                  {data.fcf_positive_years as number} 个
                </div>
              </div>
            </div>
          )}

          {stepNum === 5 && (
            <div className="mt-4 flex flex-row flex-nowrap gap-2 sm:gap-3 w-full min-w-0 overflow-x-auto">
              {data.current_pe != null && (
                <div className="bg-orange-50 rounded-xl p-2 sm:p-3 text-center flex-1 min-w-[4.25rem] shrink-0">
                  <div className="text-[10px] sm:text-xs text-orange-600">当前 PE</div>
                  <div className="text-base sm:text-lg font-bold text-orange-800">
                    {(data.current_pe as number).toFixed(1)}
                  </div>
                </div>
              )}
              {data.current_pb != null && (
                <div className="bg-sky-50 rounded-xl p-2 sm:p-3 text-center flex-1 min-w-[4.25rem] shrink-0">
                  <div className="text-[10px] sm:text-xs text-sky-600">当前 PB</div>
                  <div className="text-base sm:text-lg font-bold text-sky-800">
                    {(data.current_pb as number).toFixed(2)}
                  </div>
                </div>
              )}
              {data.pe_percentile != null && (
                <div className="bg-purple-50 rounded-xl p-2 sm:p-3 text-center flex-1 min-w-[4.25rem] shrink-0">
                  <div className="text-[10px] sm:text-xs text-purple-600">PE 分位</div>
                  <div className="text-base sm:text-lg font-bold text-purple-800">
                    {((data.pe_percentile as number) * 100).toFixed(0)}%
                  </div>
                </div>
              )}
              {data.peg != null && (
                <div className="bg-teal-50 rounded-xl p-2 sm:p-3 text-center flex-1 min-w-[4.25rem] shrink-0">
                  <div className="text-[10px] sm:text-xs text-teal-600">PEG</div>
                  <div className="text-base sm:text-lg font-bold text-teal-800">
                    {(data.peg as number).toFixed(2)}
                  </div>
                </div>
              )}
              {data.pe_mean != null && data.pe_std_dev != null && (
                <div className="bg-amber-50 rounded-xl p-2 sm:p-3 text-center flex flex-col justify-center flex-1 min-w-[6.5rem] shrink-0">
                  <div className="text-[10px] sm:text-xs text-amber-700 leading-tight">
                    安全边际股价区间
                  </div>
                  <div className="text-[9px] sm:text-[10px] text-amber-600/90 leading-tight mt-0.5">
                    历史 TTM PE：均值−1σ ~ 均值（盈利与股数不变）
                  </div>
                  {data.price_at_pe_mean == null ? (
                    <div className="text-xs sm:text-sm font-semibold text-amber-900 mt-1 leading-tight">
                      暂无现价或无法估算
                    </div>
                  ) : data.price_at_pe_minus_one_sigma != null ? (
                    <div className="text-base sm:text-lg font-bold text-amber-900 mt-0.5 leading-tight">
                      {(data.price_at_pe_minus_one_sigma as number).toFixed(2)}
                      <span className="text-amber-700 font-normal mx-0.5">–</span>
                      {(data.price_at_pe_mean as number).toFixed(2)}
                      <span className="text-[10px] sm:text-xs font-normal text-amber-700 ml-0.5">
                        元
                      </span>
                    </div>
                  ) : data.current_pe != null &&
                    (data.current_pe as number) <=
                      (data.pe_mean as number) - (data.pe_std_dev as number) ? (
                    <div className="mt-1 space-y-0.5">
                      <div className="text-xs sm:text-sm font-semibold text-amber-900 leading-tight">
                        当前 PE 已不高于均值−1σ
                      </div>
                      <div className="text-sm font-bold text-amber-900">
                        中枢参考 {(data.price_at_pe_mean as number).toFixed(2)}
                        <span className="text-[10px] font-normal text-amber-700 ml-0.5">元</span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs sm:text-sm font-semibold text-amber-900 mt-1 leading-tight">
                      暂无现价或无法估算
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
