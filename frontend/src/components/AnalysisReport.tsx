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
    <div className="mx-auto mt-4 w-full max-w-4xl space-y-4 sm:mt-8 sm:space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <h2 className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xl font-bold text-slate-900 sm:text-2xl">
            <span className="inline-flex flex-wrap items-baseline gap-x-2">
              <span>{stockName || stockCode}</span>
              {stockName && stockName !== stockCode && (
                <span className="text-base font-normal text-slate-500">{stockCode}</span>
              )}
            </span>
            {industry && (
              <span className="text-sm font-normal text-slate-600 sm:text-base sm:whitespace-nowrap">
                · {industry}
              </span>
            )}
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            {loading ? "正在进行价值投资五步法分析..." : "价值投资五步法分析报告"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/")}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-100 px-4 py-2.5 text-sm
                     text-slate-600 transition-colors hover:bg-slate-200 sm:w-auto sm:justify-start sm:py-2"
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
