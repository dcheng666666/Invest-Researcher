import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar";
import type { StockSearchResult } from "../types";

export default function HomePage() {
  const navigate = useNavigate();

  function handleSelect(stock: StockSearchResult) {
    const symbol = `${stock.market.toLowerCase()}${stock.code}`;
    navigate(`/analysis-report/${symbol}`);
  }

  return (
    <>
      <div className="text-center pt-16 pb-8">
        <h2 className="text-3xl font-bold text-slate-900 mb-3">
          发现好公司，等待好价格
        </h2>
        <p className="text-slate-500 mb-8 max-w-lg mx-auto">
          输入A股公司名称或代码，系统将自动获取近10年财务数据，
          按照价值投资五步法进行全面分析
        </p>
      </div>
      <SearchBar onSelect={handleSelect} />
    </>
  );
}
