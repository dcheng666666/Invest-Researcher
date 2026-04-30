import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";
import { useMediaQuery } from "../hooks/useMediaQuery";

const LABELS = [
  "业绩长跑",
  "血液检查",
  "厚道程度",
  "生意逻辑",
  "估值称重",
];

interface Props {
  scores: number[];
  overallScore: number;
  stockName: string;
}

export default function ScoreRadar({ scores, overallScore, stockName }: Props) {
  const mdUp = useMediaQuery("(min-width: 768px)");
  const radarHeight = mdUp ? 280 : 220;
  const angleTickFont = mdUp ? 12 : 10;
  const radiusTickFont = mdUp ? 10 : 8;

  const data = LABELS.map((label, i) => ({
    dimension: label,
    score: scores[i] ?? 0,
    fullMark: 5,
  }));

  const scoreColor =
    overallScore >= 4
      ? "text-emerald-600"
      : overallScore >= 3
        ? "text-amber-600"
        : "text-red-600";

  const scoreLabel =
    overallScore >= 4.5
      ? "强烈推荐关注"
      : overallScore >= 3.5
        ? "值得关注"
        : overallScore >= 2.5
          ? "需谨慎评估"
          : "建议规避";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
      <div className="mb-4 text-center">
        <h3 className="truncate px-1 text-base font-bold text-slate-900 sm:text-lg">
          {stockName} 综合评分
        </h3>
        <div className={`mt-2 text-3xl font-black sm:text-4xl ${scoreColor}`}>
          {overallScore.toFixed(1)}
          <span className="text-base font-normal text-slate-400 sm:text-lg"> / 5.0</span>
        </div>
        <p className={`mt-1 text-xs font-medium sm:text-sm ${scoreColor}`}>{scoreLabel}</p>
      </div>

      <ResponsiveContainer width="100%" height={radarHeight}>
        <RadarChart data={data}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: angleTickFont, fill: "#64748b" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 5]}
            tick={{ fontSize: radiusTickFont }}
          />
          <Radar
            dataKey="score"
            stroke="#3b82f6"
            fill="#3b82f6"
            fillOpacity={0.2}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
