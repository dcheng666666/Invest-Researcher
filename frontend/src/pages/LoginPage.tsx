import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3 } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object") {
    const row = detail[0] as { msg?: unknown };
    if (typeof row.msg === "string") {
      return row.msg;
    }
  }
  return "操作失败";
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { ready, needsBootstrap, authenticated, refresh } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!ready) return;
    if (authenticated) {
      navigate("/", { replace: true });
    }
  }, [ready, authenticated, navigate]);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await apiFetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => ({}))) as { detail?: unknown };
        setError(formatApiDetail(d.detail));
        return;
      }
      await refresh();
      navigate("/", { replace: true });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleBootstrap(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await apiFetch("/api/auth/bootstrap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => ({}))) as { detail?: unknown };
        setError(formatApiDetail(d.detail));
        return;
      }
      await refresh();
      navigate("/", { replace: true });
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-500 text-sm">
        加载中…
      </div>
    );
  }

  const bootstrap = needsBootstrap;

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-sm p-8 space-y-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center">
            <BarChart3 className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">
            {bootstrap ? "创建管理员" : "登录"}
          </h1>
          <p className="text-xs text-slate-500">
            {bootstrap
              ? "尚无用户：请创建首个管理员账号（至少 8 位密码）"
              : "使用已注册的账号登录"}
          </p>
        </div>

        <form
          onSubmit={(e) =>
            void (bootstrap ? handleBootstrap(e) : handleLogin(e))
          }
          className="space-y-4"
        >
          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="login-username" className="block text-xs font-medium text-slate-600 mb-1">
              用户名
            </label>
            <input
              id="login-username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              minLength={2}
              maxLength={64}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              required
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-xs font-medium text-slate-600 mb-1">
              密码（至少 8 位）
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete={bootstrap ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              required
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting
              ? bootstrap
                ? "创建中…"
                : "登录中…"
              : bootstrap
                ? "创建并进入"
                : "登录"}
          </button>
        </form>
      </div>
    </div>
  );
}
