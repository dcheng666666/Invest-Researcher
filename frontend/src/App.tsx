import type { ReactNode } from "react";
import { BarChart3 } from "lucide-react";
import {
  Routes,
  Route,
  Outlet,
  Link,
  Navigate,
  useLocation,
} from "react-router-dom";
import HomePage from "./pages/HomePage";
import ReportPage from "./pages/ReportPage";
import ValuationScreenPage from "./pages/ValuationScreenPage";
import LoginPage from "./pages/LoginPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import HistorySidebar from "./components/HistorySidebar";
import UserProfileMenu from "./components/UserProfileMenu";
import { useHistory } from "./hooks/useHistory";
import { useAuth } from "./context/AuthContext";

export interface OutletContext {
  addHistoryItem: (symbol: string, code: string, name: string) => void;
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { ready, authRequired, authenticated } = useAuth();
  const location = useLocation();

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-500 text-sm">
        加载中…
      </div>
    );
  }

  if (authRequired && !authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}

function Layout() {
  const { items, addItem, removeItem, clearAll } = useHistory();
  const {
    authEnabled,
    authenticated,
    isAdmin,
    valuationAllowed,
  } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex flex-col">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-full px-4 py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">
                价值投资五步法
              </h1>
              <p className="text-xs text-slate-500">股市企业深度基本面分析</p>
            </div>
          </div>
          <nav className="flex items-center gap-4 text-sm shrink-0">
            <Link
              to="/"
              className="text-slate-600 hover:text-slate-900 font-medium"
            >
              分析首页
            </Link>
            {valuationAllowed && (
              <Link
                to="/valuation-screen"
                className="text-slate-600 hover:text-slate-900 font-medium"
              >
                估值筛选
              </Link>
            )}
            {authEnabled && !authenticated && (
              <Link
                to="/login"
                className="text-slate-600 hover:text-slate-900 font-medium"
              >
                登录 / 升级
              </Link>
            )}
            {authEnabled && authenticated && isAdmin && (
              <Link
                to="/admin/users"
                className="text-slate-600 hover:text-slate-900 font-medium"
              >
                用户管理
              </Link>
            )}
            {authEnabled && authenticated && <UserProfileMenu />}
          </nav>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <HistorySidebar items={items} removeItem={removeItem} clearAll={clearAll} />
        <main className="flex-1 overflow-y-auto px-4 py-8">
          <div className="max-w-5xl mx-auto">
            <Outlet context={{ addHistoryItem: addItem } satisfies OutletContext} />
          </div>
        </main>
      </div>

      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        本工具仅供学习研究使用，不构成任何投资建议。投资有风险，入市需谨慎。
      </footer>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="analysis-report/:symbol" element={<ReportPage />} />
        <Route path="valuation-screen" element={<ValuationScreenPage />} />
        <Route path="admin/users" element={<AdminUsersPage />} />
      </Route>
    </Routes>
  );
}

export default App;
