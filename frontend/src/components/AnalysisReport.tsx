import { useNavigate } from "react-router-dom";
import type { AnalysisState } from "../types";
import StepCard from "./StepCard";
import ScoreRadar from "./ScoreRadar";
import { RotateCcw } from "lucide-react";

interface Props {
  state: AnalysisState;
}

export default function AnalysisReport({ state }: Props) {
  const navigate = useNavigate();
  const { stockName, stockCode, industry, steps, complete, loading } = state;

  return (
    <div className="w-full max-w-4xl mx-auto mt-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="inline-flex flex-wrap items-baseline gap-x-2">
              <span>{stockName || stockCode}</span>
              {stockName && stockName !== stockCode && (
                <span className="text-base font-normal text-slate-500">{stockCode}</span>
              )}
            </span>
            {industry && (
              <span className="text-base font-normal text-slate-600 whitespace-nowrap">
                · {industry}
              </span>
            )}
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            {loading ? "正在进行价值投资五步法分析..." : "价值投资五步法分析报告"}
          </p>
        </div>
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 bg-slate-100
                     rounded-xl hover:bg-slate-200 transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          重新分析
        </button>
      </div>

      {complete && (
        <ScoreRadar
          scores={complete.scores}
          overallScore={complete.overall_score}
          stockName={stockName}
        />
      )}

      <div className="grid gap-6">
        {[1, 2, 3, 4, 5].map((stepNum) => (
          <StepCard key={stepNum} stepNum={stepNum} event={steps[stepNum]} />
        ))}
      </div>
    </div>
  );
}
