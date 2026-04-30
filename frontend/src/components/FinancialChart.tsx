import {
  LineChart,
  Line,
  BarChart,
  Bar,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { AnnualRevenueChartPoint, PeriodMetric } from "../types";
import { useMediaQuery } from "../hooks/useMediaQuery";

interface ReferenceLineSpec {
  y: number;
  label: string;
  color?: string;
  strokeDasharray?: string;
}

interface LineChartProps {
  title: string;
  series: { data: PeriodMetric[]; name: string; color: string }[];
  yAxisFormatter?: (v: number) => string;
  referenceLine?: ReferenceLineSpec;
  referenceLines?: ReferenceLineSpec[];
  sharedPeriods?: string[];
  rightMargin?: number;
  autoClampY?: boolean;
}

function metricPeriod(m: PeriodMetric): string {
  return m.period;
}

function quarterTickFormatter(value: string) {
  if (!value.includes("Q")) return value;
  const [year, q] = value.split("Q");
  if (q === "4") return year;
  return `Q${q}`;
}



function computeAutoClamp(
  chartData: Record<string, string | number | null>[],
  seriesNames: string[],
  refLineY?: number,
): [number, number] | null {
  const values: number[] = [];
  for (const entry of chartData) {
    for (const name of seriesNames) {
      const v = entry[name];
      if (typeof v === "number" && isFinite(v)) values.push(v);
    }
  }
  if (values.length < 6) return null;

  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  const q1 = sorted[Math.floor(n * 0.25)];
  const q3 = sorted[Math.floor(n * 0.75)];
  const iqr = q3 - q1;
  if (iqr <= 0) return null;

  let lower = q1 - 2 * iqr;
  let upper = q3 + 2 * iqr;

  const dataMin = sorted[0];
  const dataMax = sorted[n - 1];
  if (dataMin >= lower && dataMax <= upper) return null;

  if (upper - lower > (dataMax - dataMin) * 0.7) return null;

  if (refLineY != null) {
    lower = Math.min(lower, refLineY);
    upper = Math.max(upper, refLineY);
  }

  const pad = (upper - lower) * 0.08;
  return [lower - pad, upper + pad];
}

function renderClampedDot(
  seriesName: string,
  color: string,
  domain: [number, number],
  formatter?: (v: number) => string,
) {
  return (props: Record<string, unknown>) => {
    const cx = props.cx as number;
    const cy = props.cy as number;
    const payload = props.payload as Record<string, unknown> | undefined;
    if (cx == null || cy == null) return <g />;
    const origValue = payload?.[`_orig_${seriesName}`] as number | undefined;
    if (origValue != null) {
      const label = formatter ? formatter(origValue) : origValue.toFixed(2);
      const isHigh = origValue > domain[1];
      return (
        <g>
          <polygon
            points={
              isHigh
                ? `${cx},${cy - 5} ${cx - 3.5},${cy + 2} ${cx + 3.5},${cy + 2}`
                : `${cx},${cy + 5} ${cx - 3.5},${cy - 2} ${cx + 3.5},${cy - 2}`
            }
            fill={color}
          />
          <text
            x={cx}
            y={isHigh ? cy + 15 : cy - 9}
            textAnchor="middle"
            fill={color}
            fontSize={8}
            fontWeight="bold"
          >
            {label}
          </text>
        </g>
      );
    }
    return <circle cx={cx} cy={cy} r={2} fill={color} stroke={color} />;
  };
}

export function MetricLineChart({
  title,
  series,
  yAxisFormatter,
  referenceLine,
  referenceLines: referenceLinesProp,
  sharedPeriods,
  rightMargin,
  autoClampY,
}: LineChartProps) {
  const mdUp = useMediaQuery("(min-width: 768px)");
  const resolvedRightMargin =
    rightMargin != null
      ? mdUp
        ? rightMargin
        : Math.max(8, Math.round(rightMargin * 0.45))
      : undefined;
  const lineChartHeight = mdUp ? 260 : 220;
  const yAxisWidth = mdUp ? 70 : 48;
  const tickFontY = mdUp ? 12 : 10;
  const tickFontX = mdUp ? 10 : 8;

  const ownPeriods = new Set<string>();
  series.forEach((s) => s.data.forEach((d) => ownPeriods.add(metricPeriod(d))));
  const sortedPeriods = sharedPeriods ?? Array.from(ownPeriods).sort();

  const chartData = sortedPeriods.map((period) => {
    const entry: Record<string, string | number | null> = { period };
    series.forEach((s) => {
      const point = s.data.find((d) => metricPeriod(d) === period);
      entry[s.name] = point ? point.value : null;
    });
    return entry;
  });

  if (chartData.length === 0) return null;

  const allRefLines: ReferenceLineSpec[] = [
    ...(referenceLine ? [referenceLine] : []),
    ...(referenceLinesProp ?? []),
  ];

  const seriesNames = series.map((s) => s.name);
  const clampDomain = autoClampY
    ? computeAutoClamp(chartData, seriesNames, referenceLine?.y)
    : null;

  let displayData = chartData;
  if (clampDomain) {
    const [lo, hi] = clampDomain;
    displayData = chartData.map((entry) => {
      const clamped: Record<string, string | number | null> = { ...entry };
      for (const name of seriesNames) {
        const v = clamped[name];
        if (typeof v === "number" && (v < lo || v > hi)) {
          (clamped as Record<string, unknown>)[`_orig_${name}`] = v;
          clamped[name] = Math.max(lo, Math.min(hi, v));
        }
      }
      return clamped;
    });
  }

  const hasQuarters = sortedPeriods.some((p) => p.includes("Q"));
  const hasMonths = sortedPeriods.some((p) => /^\d{4}-\d{2}$/.test(p));
  const q1Ticks = hasQuarters
    ? sortedPeriods.filter((p) => p.endsWith("Q1"))
    : undefined;
  const janTicks = hasMonths
    ? sortedPeriods.filter((p) => p.endsWith("-01"))
    : undefined;

  const xAxisProps = q1Ticks
    ? {
        ticks: q1Ticks,
        tickFormatter: (v: string) => v.includes("Q") ? v.split("Q")[0] : v,
      }
    : janTicks
      ? {
          ticks: janTicks,
          tickFormatter: (v: string) => v.slice(0, 4),
        }
      : {
          ticks: sortedPeriods,
          tickFormatter: quarterTickFormatter,
          interval: displayData.length > 20 ? 1 : 0,
        };

  return (
    <div className="mt-4">
      <h4 className="text-sm font-medium text-slate-600 mb-2">{title}</h4>
      <ResponsiveContainer width="100%" height={lineChartHeight}>
        <LineChart
          data={displayData}
          margin={resolvedRightMargin != null ? { right: resolvedRightMargin } : undefined}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="period"
            tick={{ fontSize: tickFontX }}
            {...xAxisProps}
            height={30}
          />
          <YAxis
            tick={{ fontSize: tickFontY }}
            tickFormatter={yAxisFormatter}
            width={yAxisWidth}
            {...(clampDomain ? { domain: clampDomain, allowDataOverflow: true } : {})}
          />
          <Tooltip
            formatter={(value, name, entry) => {
              const origKey = `_orig_${String(name)}`;
              const entryPayload = (entry as { payload?: Record<string, unknown> })?.payload;
              const origValue = entryPayload?.[origKey];
              const v = typeof origValue === "number"
                ? origValue
                : typeof value === "number" ? value : Number(value);
              const formatted = yAxisFormatter ? yAxisFormatter(v) : v.toFixed(2);
              return [formatted, String(name ?? "")];
            }}
            labelFormatter={(label) => `报告期: ${String(label)}`}
          />
          <Legend />
          {allRefLines.map((ref, i) => (
            <ReferenceLine
              key={i}
              y={ref.y}
              stroke={ref.color ?? "#ef4444"}
              strokeDasharray={ref.strokeDasharray ?? "5 5"}
            />
          ))}
          {series.map((s) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={s.color}
              strokeWidth={2}
              dot={
                hasMonths
                  ? false
                  : clampDomain
                    ? renderClampedDot(s.name, s.color, clampDomain, yAxisFormatter)
                    : { r: 2 }
              }
              activeDot={hasMonths ? { r: 3 } : { r: 4 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      {allRefLines.some((ref) => ref.label) && (
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 mt-1">
          {allRefLines
            .filter((ref) => ref.label)
            .map((ref, i) => (
              <span key={i} className="inline-flex items-center gap-1.5 text-xs">
                <svg width="20" height="8">
                  <line
                    x1="0" y1="4" x2="20" y2="4"
                    stroke={ref.color ?? "#ef4444"}
                    strokeWidth="1.5"
                    strokeDasharray={ref.strokeDasharray === "2 2" ? "3 2" : "5 3"}
                  />
                </svg>
                <span style={{ color: ref.color ?? "#ef4444" }}>{ref.label}</span>
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

interface BarChartProps {
  title: string;
  data: PeriodMetric[];
  name: string;
  color: string;
  yAxisFormatter?: (v: number) => string;
  sharedPeriods?: string[];
}

export function MetricBarChart({
  title,
  data,
  name,
  color,
  yAxisFormatter,
  sharedPeriods,
}: BarChartProps) {
  const mdUp = useMediaQuery("(min-width: 768px)");
  const barChartHeight = mdUp ? 220 : 190;
  const yAxisWidthBar = mdUp ? 60 : 44;
  const tickFontYBar = mdUp ? 12 : 10;
  const tickFontXBar = mdUp ? 10 : 8;

  if (data.length === 0) return null;

  let chartData: Record<string, string | number | null>[];
  let sortedPeriods: string[];

  if (sharedPeriods) {
    sortedPeriods = sharedPeriods;
    const dataByPeriod = new Map(data.map((d) => [metricPeriod(d), d]));
    chartData = sortedPeriods.map((period) => {
      const row = dataByPeriod.get(period);
      const dc = row?.distribution_count;
      return {
        period,
        [name]: row?.value ?? null,
        ...(typeof dc === "number" ? { distribution_count: dc } : {}),
      };
    });
  } else {
    chartData = data.map((d) => {
      const dc = d.distribution_count;
      return {
        period: metricPeriod(d),
        [name]: d.value,
        ...(typeof dc === "number" ? { distribution_count: dc } : {}),
      };
    });
    sortedPeriods = chartData.map((d) => d.period as string);
  }

  const hasQuarters = sortedPeriods.some((p) => p.includes("Q"));
  const q1Ticks = hasQuarters
    ? sortedPeriods.filter((p) => p.endsWith("Q1"))
    : undefined;

  return (
    <div className="mt-4">
      <h4 className="text-sm font-medium text-slate-600 mb-2">{title}</h4>
      <ResponsiveContainer width="100%" height={barChartHeight}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="period"
            tick={{ fontSize: tickFontXBar }}
            {...(q1Ticks
              ? {
                  ticks: q1Ticks,
                  tickFormatter: (v: string) => v.includes("Q") ? v.split("Q")[0] : v,
                }
              : {
                  ticks: sortedPeriods,
                  tickFormatter: quarterTickFormatter,
                  interval: chartData.length > 20 ? 1 : 0,
                }
            )}
            height={30}
          />
          <YAxis
            tick={{ fontSize: tickFontYBar }}
            tickFormatter={yAxisFormatter}
            width={yAxisWidthBar}
          />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0];
              const raw = p.value;
              const v =
                raw == null || raw === ""
                  ? NaN
                  : typeof raw === "number"
                    ? raw
                    : Number(raw);
              const formatted = Number.isFinite(v)
                ? yAxisFormatter
                  ? yAxisFormatter(v)
                  : v.toFixed(2)
                : "—";
              const pl = p.payload as Record<string, unknown> | undefined;
              const distCount = pl?.distribution_count;
              return (
                <div
                  className="rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-sm"
                  style={{ outline: "none" }}
                >
                  <p className="m-0 text-slate-600">{`报告期: ${String(label ?? "")}`}</p>
                  {typeof distCount === "number" ? (
                    <p className="m-0 mt-0.5 text-slate-600">分红次数: {distCount}</p>
                  ) : null}
                  <p className="m-0 mt-0.5 text-slate-800">
                    <span className="text-slate-500">{name}: </span>
                    {formatted}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey={name} fill={color} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface DualBarChartProps {
  title: string;
  series: { data: PeriodMetric[]; name: string; color: string }[];
  yAxisFormatter?: (v: number) => string;
  sharedPeriods?: string[];
  rightMargin?: number;
}

export function DualBarChart({
  title,
  series,
  yAxisFormatter,
  sharedPeriods,
  rightMargin,
}: DualBarChartProps) {
  const mdUp = useMediaQuery("(min-width: 768px)");
  const resolvedRightMarginDual =
    rightMargin != null
      ? mdUp
        ? rightMargin
        : Math.max(8, Math.round(rightMargin * 0.45))
      : undefined;
  const dualBarHeight = mdUp ? 260 : 220;
  const yAxisWidthDual = mdUp ? 70 : 48;
  const tickFontYDual = mdUp ? 12 : 10;
  const tickFontXDual = mdUp ? 10 : 8;

  const ownPeriods = new Set<string>();
  series.forEach((s) => s.data.forEach((d) => ownPeriods.add(metricPeriod(d))));
  const sortedPeriods = sharedPeriods ?? Array.from(ownPeriods).sort();

  const chartData = sortedPeriods.map((period) => {
    const entry: Record<string, string | number | null> = { period };
    series.forEach((s) => {
      const point = s.data.find((d) => metricPeriod(d) === period);
      entry[s.name] = point ? point.value : null;
    });
    return entry;
  });

  if (chartData.length === 0) return null;

  const q1Ticks = sortedPeriods.filter((p) => p.endsWith("Q1"));

  return (
    <div className="mt-4">
      <h4 className="text-sm font-medium text-slate-600 mb-2">{title}</h4>
      <ResponsiveContainer width="100%" height={dualBarHeight}>
        <BarChart
          data={chartData}
          margin={resolvedRightMarginDual != null ? { right: resolvedRightMarginDual } : undefined}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="period"
            tick={{ fontSize: tickFontXDual }}
            ticks={q1Ticks}
            tickFormatter={(v: string) => v.includes("Q") ? v.split("Q")[0] : v}
            height={30}
          />
          <YAxis
            tick={{ fontSize: tickFontYDual }}
            tickFormatter={yAxisFormatter}
            width={yAxisWidthDual}
          />
          <Tooltip
            formatter={(value, name) => {
              const v = typeof value === "number" ? value : Number(value);
              const formatted = yAxisFormatter
                ? yAxisFormatter(v)
                : v.toFixed(2);
              return [formatted, String(name ?? "")];
            }}
            labelFormatter={(label) => `报告期: ${String(label)}`}
          />
          <Legend />
          {series.map((s) => (
            <Bar
              key={s.name}
              dataKey={s.name}
              fill={s.color}
              radius={[2, 2, 0, 0]}
              barSize={14}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function monthToQuarter(ym: string): string {
  const [y, m] = ym.split("-");
  const q = Math.ceil(parseInt(m, 10) / 3);
  return `${y}Q${q}`;
}

function quarterEndMonth(period: string): string {
  const [year, qStr] = period.split("Q");
  const month = parseInt(qStr, 10) * 3;
  return `${year}-${month.toString().padStart(2, "0")}`;
}

function isMonthlyPeriod(p: string): boolean {
  return /^\d{4}-\d{2}$/.test(p);
}

interface RevenueMarketCapChartProps {
  title: string;
  ttmRevenueChart: AnnualRevenueChartPoint[];
  ttmProfitChart?: AnnualRevenueChartPoint[];
  marketCapMonthly: PeriodMetric[];
  revenueLabel?: string;
  profitLabel?: string;
  marketCapLabel?: string;
  caption?: string;
  // Monthly periods (YYYY-MM). When provided, the chart switches to a monthly
  // category X-axis so it can align horizontally with sibling monthly charts
  // (e.g. PE-TTM monthly trend).
  sharedPeriods?: string[];
}

export function RevenueMarketCapChart({
  title,
  ttmRevenueChart,
  ttmProfitChart = [],
  marketCapMonthly,
  revenueLabel = "TTM营收",
  profitLabel = "TTM扣非净利润",
  marketCapLabel = "总市值（季末）",
  caption = "柱状图为各季度的TTM（过去12个月滚动）营收与扣非净利润，折线为季末月均市值。业绩持续上行而市值停滞 → 估值偏低；反之则偏高。",
  sharedPeriods,
}: RevenueMarketCapChartProps) {
  const mdUp = useMediaQuery("(min-width: 768px)");
  const composedHeight = mdUp ? 300 : 252;
  const yAxisWide = mdUp ? 70 : 50;
  const tickFontComposed = mdUp ? 11 : 9;
  const axisLabelFont = mdUp ? 11 : 9;

  if (ttmRevenueChart.length === 0 && marketCapMonthly.length === 0) return null;

  const monthlyMode = !!sharedPeriods?.length && sharedPeriods.every(isMonthlyPeriod);

  let chartData: Record<string, string | number | null>[];
  let xTicks: string[];
  let xTickFormatter: (v: string) => string;

  if (monthlyMode && sharedPeriods) {
    // Monthly category axis: place quarterly TTM bars at the quarter-end month
    // and let the market-cap line consume the raw monthly series.
    const revByMonth = new Map<string, number>();
    ttmRevenueChart.forEach((p) =>
      revByMonth.set(quarterEndMonth(p.period), p.value),
    );
    const profitByMonth = new Map<string, number>();
    ttmProfitChart.forEach((p) =>
      profitByMonth.set(quarterEndMonth(p.period), p.value),
    );
    const capByMonth = new Map<string, number>();
    marketCapMonthly.forEach((d) => capByMonth.set(d.period, d.value));

    chartData = sharedPeriods.map((period) => ({
      period,
      revenueBar: revByMonth.get(period) ?? null,
      profitBar: profitByMonth.get(period) ?? null,
      marketCap: capByMonth.get(period) ?? null,
    }));
    xTicks = sharedPeriods.filter((p) => p.endsWith("-01"));
    xTickFormatter = (v: string) => v.slice(0, 4);
  } else {
    const revByQ = new Map<string, number>();
    ttmRevenueChart.forEach((p) => revByQ.set(p.period, p.value));

    const profitByQ = new Map<string, number>();
    ttmProfitChart.forEach((p) => profitByQ.set(p.period, p.value));

    // Pick the latest month per quarter so the line tracks a single value per
    // bar bucket — avoids 3x overplotting when monthly market cap is dense.
    const qCapEntries = new Map<string, { month: string; value: number }>();
    marketCapMonthly.forEach((d) => {
      const ym = d.period;
      const q = monthToQuarter(ym);
      const prev = qCapEntries.get(q);
      if (!prev || ym > prev.month) {
        qCapEntries.set(q, { month: ym, value: d.value });
      }
    });
    const capByQ = new Map<string, number>();
    qCapEntries.forEach(({ value }, q) => capByQ.set(q, value));

    const periodSet = new Set<string>();
    ttmRevenueChart.forEach((p) => periodSet.add(p.period));
    ttmProfitChart.forEach((p) => periodSet.add(p.period));
    capByQ.forEach((_, k) => periodSet.add(k));
    const sortedPeriods = Array.from(periodSet).sort();
    if (sortedPeriods.length === 0) return null;

    chartData = sortedPeriods.map((period) => ({
      period,
      revenueBar: revByQ.get(period) ?? null,
      profitBar: profitByQ.get(period) ?? null,
      marketCap: capByQ.get(period) ?? null,
    }));
    xTicks = sortedPeriods.filter((p) => p.endsWith("Q1"));
    xTickFormatter = (v: string) => (v.includes("Q") ? v.split("Q")[0] : v);
  }

  if (chartData.length === 0) return null;

  const yiFormatter = (v: number) => `${v.toFixed(0)}亿`;

  return (
    <div className="mt-4">
      <h4 className="text-sm font-medium text-slate-600 mb-2">{title}</h4>
      <ResponsiveContainer width="100%" height={composedHeight}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="period"
            ticks={xTicks}
            tick={{ fontSize: mdUp ? 10 : 8 }}
            tickFormatter={xTickFormatter}
            height={30}
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: tickFontComposed }}
            tickFormatter={yiFormatter}
            width={yAxisWide}
            label={{
              value: "业绩（亿）",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: axisLabelFont, fill: "#475569" },
            }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: tickFontComposed }}
            tickFormatter={yiFormatter}
            width={yAxisWide}
            label={{
              value: marketCapLabel,
              angle: 90,
              position: "insideRight",
              style: { fontSize: axisLabelFont, fill: "#ef4444" },
            }}
          />
          <Tooltip
            formatter={(value, name) => {
              const v = typeof value === "number" ? value : Number(value);
              return [`${v.toFixed(1)}亿`, String(name ?? "")];
            }}
            labelFormatter={(label) => `报告期: ${String(label)}`}
          />
          <Legend />
          <Bar
            yAxisId="left"
            name={revenueLabel}
            dataKey="revenueBar"
            fill="#3b82f6"
            radius={[2, 2, 0, 0]}
            barSize={14}
          />
          <Bar
            yAxisId="left"
            name={profitLabel}
            dataKey="profitBar"
            fill="#10b981"
            radius={[2, 2, 0, 0]}
            barSize={14}
          />
          <Line
            yAxisId="right"
            name={marketCapLabel}
            type="monotone"
            dataKey="marketCap"
            stroke="#ef4444"
            strokeWidth={2}
            dot={false}
            connectNulls
            activeDot={{ r: 4 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
      {caption && (
        <p className="text-xs text-slate-500 mt-2 leading-relaxed">{caption}</p>
      )}
    </div>
  );
}
