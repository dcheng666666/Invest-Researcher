import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

type UserRow = {
  id: number;
  username: string;
  is_admin: boolean;
  membership_tier: string;
  created_at: string;
};

type Tier = "none" | "basic" | "premium";

type RowDraft = { tier: Tier; is_admin: boolean };

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

function normalizeTier(raw: string): Tier {
  if (raw === "basic" || raw === "premium") return raw;
  return "none";
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [newIsAdmin, setNewIsAdmin] = useState(false);
  const [newTier, setNewTier] = useState<Tier>("none");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [draftById, setDraftById] = useState<Record<number, RowDraft>>({});
  const [newPwById, setNewPwById] = useState<Record<number, string>>({});
  const [rowMsg, setRowMsg] = useState<Record<number, string | null>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/admin/users");
      if (!res.ok) {
        setError(`加载失败 (${res.status})`);
        setUsers([]);
        return;
      }
      const j = (await res.json()) as { users?: UserRow[] };
      const list = Array.isArray(j.users) ? j.users : [];
      setUsers(list);
      const drafts: Record<number, RowDraft> = {};
      for (const u of list) {
        drafts[u.id] = {
          tier: normalizeTier(u.membership_tier),
          is_admin: u.is_admin,
        };
      }
      setDraftById(drafts);
      setNewPwById({});
      setRowMsg({});
    } catch {
      setError("网络错误");
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      const res = await apiFetch("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          password,
          is_admin: newIsAdmin,
          membership_tier: newTier,
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => ({}))) as { detail?: unknown };
        setFormError(formatApiDetail(d.detail));
        return;
      }
      setUsername("");
      setPassword("");
      setNewIsAdmin(false);
      setNewTier("none");
      await load();
    } finally {
      setSubmitting(false);
    }
  }

  async function saveRowProfile(userId: number) {
    const d = draftById[userId];
    if (!d) return;
    setBusyId(userId);
    setRowMsg((m) => ({ ...m, [userId]: null }));
    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          membership_tier: d.tier,
          is_admin: d.is_admin,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
        setRowMsg((m) => ({
          ...m,
          [userId]: formatApiDetail(body.detail),
        }));
        return;
      }
      setRowMsg((m) => ({ ...m, [userId]: "已保存" }));
      await load();
    } catch {
      setRowMsg((m) => ({ ...m, [userId]: "网络错误" }));
    } finally {
      setBusyId(null);
    }
  }

  async function saveRowPassword(userId: number) {
    const pw = (newPwById[userId] ?? "").trim();
    if (pw.length < 8) {
      setRowMsg((m) => ({ ...m, [userId]: "新密码至少 8 位" }));
      return;
    }
    setBusyId(userId);
    setRowMsg((m) => ({ ...m, [userId]: null }));
    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pw }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
        setRowMsg((m) => ({
          ...m,
          [userId]: formatApiDetail(body.detail),
        }));
        return;
      }
      setNewPwById((p) => ({ ...p, [userId]: "" }));
      setRowMsg((m) => ({ ...m, [userId]: "密码已更新" }));
    } catch {
      setRowMsg((m) => ({ ...m, [userId]: "网络错误" }));
    } finally {
      setBusyId(null);
    }
  }

  async function removeUser(userId: number) {
    if (
      !window.confirm(
        "确定删除该用户？此操作不可撤销（须至少保留一名管理员）。",
      )
    ) {
      return;
    }
    setBusyId(userId);
    setRowMsg((m) => ({ ...m, [userId]: null }));
    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
        setRowMsg((m) => ({
          ...m,
          [userId]: formatApiDetail(body.detail),
        }));
        return;
      }
      await load();
    } catch {
      setRowMsg((m) => ({ ...m, [userId]: "网络错误" }));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">用户管理</h2>
          <p className="text-sm text-slate-500 mt-1">
            创建用户，并编辑会员档位、管理员权限、重置密码或删除用户
          </p>
        </div>
        <Link
          to="/"
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          返回首页
        </Link>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">新建用户</h3>
        <form onSubmit={(e) => void handleCreate(e)} className="space-y-4 max-w-md">
          {formError && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {formError}
            </div>
          )}
          <div>
            <label
              htmlFor="new-username"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              用户名
            </label>
            <input
              id="new-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              minLength={2}
              maxLength={64}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label
              htmlFor="new-password"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              初始密码（至少 8 位）
            </label>
            <input
              id="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              required
            />
          </div>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            会员档位
            <select
              value={newTier}
              onChange={(e) => setNewTier(e.target.value as Tier)}
              className="border border-slate-200 rounded-lg px-2 py-2 text-sm text-slate-900"
            >
              <option value="none">非会员（10 次报告/日）</option>
              <option value="basic">初级（50 次/日）</option>
              <option value="premium">高级（不限 + 估值筛选）</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={newIsAdmin}
              onChange={(e) => setNewIsAdmin(e.target.checked)}
              className="rounded border-slate-300"
            />
            设为管理员
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "创建中…" : "创建用户"}
          </button>
        </form>
      </section>

      <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm overflow-x-auto">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">用户列表</h3>
        {loading ? (
          <p className="text-sm text-slate-500">加载中…</p>
        ) : users.length === 0 ? (
          <p className="text-sm text-slate-500">暂无用户</p>
        ) : (
          <table className="w-full text-sm text-left border-collapse min-w-[720px]">
            <thead>
              <tr className="border-b border-slate-200 text-slate-600">
                <th className="py-2 pr-3 font-medium">ID</th>
                <th className="py-2 pr-3 font-medium">用户名</th>
                <th className="py-2 pr-3 font-medium">会员</th>
                <th className="py-2 pr-3 font-medium">管理员</th>
                <th className="py-2 pr-3 font-medium">创建时间</th>
                <th className="py-2 pr-3 font-medium">新密码</th>
                <th className="py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const draft = draftById[u.id];
                const busy = busyId === u.id;
                const msg = rowMsg[u.id];
                return (
                  <tr
                    key={u.id}
                    className="border-b border-slate-100 text-slate-800 align-top"
                  >
                    <td className="py-3 pr-3 tabular-nums">{u.id}</td>
                    <td className="py-3 pr-3 font-medium whitespace-nowrap">
                      {u.username}
                    </td>
                    <td className="py-3 pr-3">
                      {draft ? (
                        <select
                          value={draft.tier}
                          disabled={busy}
                          onChange={(e) =>
                            setDraftById((prev) => ({
                              ...prev,
                              [u.id]: {
                                ...prev[u.id],
                                tier: e.target.value as Tier,
                              },
                            }))
                          }
                          className="max-w-[10rem] border border-slate-200 rounded-lg px-2 py-1.5 text-xs text-slate-900"
                        >
                          <option value="none">非会员</option>
                          <option value="basic">初级</option>
                          <option value="premium">高级</option>
                        </select>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3 pr-3">
                      {draft ? (
                        <label className="inline-flex items-center gap-1.5 text-xs">
                          <input
                            type="checkbox"
                            checked={draft.is_admin}
                            disabled={busy}
                            onChange={(e) =>
                              setDraftById((prev) => ({
                                ...prev,
                                [u.id]: {
                                  ...prev[u.id],
                                  is_admin: e.target.checked,
                                },
                              }))
                            }
                            className="rounded border-slate-300"
                          />
                          管理员
                        </label>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3 pr-3 text-slate-500 whitespace-nowrap text-xs">
                      {u.created_at}
                    </td>
                    <td className="py-3 pr-3">
                      <input
                        type="password"
                        autoComplete="new-password"
                        placeholder="至少 8 位"
                        value={newPwById[u.id] ?? ""}
                        disabled={busy}
                        onChange={(e) =>
                          setNewPwById((p) => ({
                            ...p,
                            [u.id]: e.target.value,
                          }))
                        }
                        className="w-36 max-w-full border border-slate-200 rounded-lg px-2 py-1.5 text-xs"
                      />
                    </td>
                    <td className="py-3">
                      <div className="flex flex-col gap-2 items-start">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            disabled={busy || !draft}
                            onClick={() => void saveRowProfile(u.id)}
                            className="px-2.5 py-1 rounded-lg bg-slate-800 text-white text-xs font-medium hover:bg-slate-900 disabled:opacity-50"
                          >
                            保存档位/角色
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void saveRowPassword(u.id)}
                            className="px-2.5 py-1 rounded-lg border border-slate-300 text-slate-800 text-xs font-medium hover:bg-slate-50 disabled:opacity-50"
                          >
                            更新密码
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void removeUser(u.id)}
                            className="px-2.5 py-1 rounded-lg border border-red-200 text-red-700 text-xs font-medium hover:bg-red-50 disabled:opacity-50"
                          >
                            删除
                          </button>
                        </div>
                        {msg && (
                          <p
                            className={
                              msg.startsWith("已") || msg.startsWith("密码")
                                ? "text-xs text-emerald-600"
                                : "text-xs text-red-600"
                            }
                          >
                            {msg}
                          </p>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
