import type { ReactNode } from "react";
import { startTransition, useEffect, useState } from "react";
import { BarChart3, History, Menu, X } from "lucide-react";
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
  const location = useLocation();
  const { items, addItem, removeItem, clearAll } = useHistory();
  const {
    authEnabled,
    authenticated,
    isAdmin,
    valuationAllowed,
  } = useAuth();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    startTransition(() => {
      setHistoryOpen(false);
      setNavOpen(false);
    });
  }, [location.pathname]);

  const navLinkClass =
    "block rounded-lg px-3 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 active:bg-slate-100";

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex flex-col">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-full px-3 sm:px-4 py-3 sm:py-4 flex items-center justify-between gap-2 sm:gap-3">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <div className="w-8 h-8 sm:w-9 sm:h-9 bg-blue-600 rounded-xl flex items-center justify-center shrink-0">
              <BarChart3 className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base sm:text-lg font-bold text-slate-900 truncate">
                价值投资五步法
              </h1>
              <p className="hidden truncate text-[10px] text-slate-500 sm:block sm:text-xs">
                股市企业深度基本面分析
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1 sm:gap-2 shrink-0">
            <button
              type="button"
              className="md:hidden flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              onClick={() => setHistoryOpen(true)}
              aria-label="打开历史记录"
            >
              <History className="h-5 w-5" aria-hidden />
            </button>
            <button
              type="button"
              className="md:hidden flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              onClick={() => setNavOpen(true)}
              aria-label="打开导航菜单"
            >
              <Menu className="h-5 w-5" aria-hidden />
            </button>

            <nav className="hidden md:flex items-center gap-4 text-sm shrink-0">
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
        </div>
      </header>

      {/* Mobile history drawer */}
      {historyOpen && (
        <div className="md:hidden">
          <button
            type="button"
            aria-label="关闭历史记录"
            className="fixed inset-0 z-40 bg-slate-900/45"
            onClick={() => setHistoryOpen(false)}
          />
          <div
            className="fixed bottom-0 left-0 top-16 z-50 flex w-[min(18rem,calc(100vw-1.5rem))] flex-col overflow-hidden border-r border-slate-200 bg-white shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-label="历史记录"
          >
            <HistorySidebar
              items={items}
              removeItem={removeItem}
              clearAll={clearAll}
              onClose={() => setHistoryOpen(false)}
              className="border-0 bg-white"
            />
          </div>
        </div>
      )}

      {/* Mobile navigation drawer */}
      {navOpen && (
        <div className="md:hidden">
          <button
            type="button"
            aria-label="关闭导航菜单"
            className="fixed inset-0 z-40 bg-slate-900/45"
            onClick={() => setNavOpen(false)}
          />
          <div
            className="fixed bottom-0 right-0 top-16 z-50 flex w-[min(20rem,85vw)] flex-col border-l border-slate-200 bg-white shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-label="导航菜单"
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 shrink-0">
              <span className="text-sm font-semibold text-slate-800">菜单</span>
              <button
                type="button"
                className="flex h-10 w-10 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                onClick={() => setNavOpen(false)}
                aria-label="关闭"
              >
                <X className="h-5 w-5" aria-hidden />
              </button>
            </div>
            <nav className="flex flex-col gap-1 p-3 overflow-y-auto">
              <Link to="/" className={navLinkClass} onClick={() => setNavOpen(false)}>
                分析首页
              </Link>
              {valuationAllowed && (
                <Link
                  to="/valuation-screen"
                  className={navLinkClass}
                  onClick={() => setNavOpen(false)}
                >
                  估值筛选
                </Link>
              )}
              {authEnabled && !authenticated && (
                <Link to="/login" className={navLinkClass} onClick={() => setNavOpen(false)}>
                  登录 / 升级
                </Link>
              )}
              {authEnabled && authenticated && isAdmin && (
                <Link
                  to="/admin/users"
                  className={navLinkClass}
                  onClick={() => setNavOpen(false)}
                >
                  用户管理
                </Link>
              )}
              {authEnabled && authenticated && (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <p className="mb-2 px-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                    账户
                  </p>
                  <UserProfileMenu />
                </div>
              )}
            </nav>
          </div>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="hidden min-h-0 w-64 shrink-0 flex-col border-r border-slate-200 bg-white/60 backdrop-blur-sm md:flex md:flex-col">
          <HistorySidebar
            items={items}
            removeItem={removeItem}
            clearAll={clearAll}
            className="border-0 bg-transparent"
          />
        </div>
        <main className="flex-1 min-w-0 overflow-y-auto px-3 py-4 sm:px-4 sm:py-6 md:px-4 md:py-8">
          <div className="max-w-5xl mx-auto">
            <Outlet context={{ addHistoryItem: addItem } satisfies OutletContext} />
          </div>
        </main>
      </div>

      <footer className="border-t border-slate-200 py-4 sm:py-6 text-center text-xs text-slate-400 px-2">
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
