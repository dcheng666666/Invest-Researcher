import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

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
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
      <div className="text-center mb-4">
        <h3 className="text-lg font-bold text-slate-900">
          {stockName} 综合评分
        </h3>
        <div className={`text-4xl font-black mt-2 ${scoreColor}`}>
          {overallScore.toFixed(1)}
          <span className="text-lg font-normal text-slate-400"> / 5.0</span>
        </div>
        <p className={`text-sm mt-1 font-medium ${scoreColor}`}>{scoreLabel}</p>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <RadarChart data={data}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: 12, fill: "#64748b" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 5]}
            tick={{ fontSize: 10 }}
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
