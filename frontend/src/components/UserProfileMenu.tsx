import { useCallback, useEffect, useRef, useState } from "react";
import { LogOut, User } from "lucide-react";
import { useAuth } from "../context/AuthContext";

function membershipTierLabel(tier: string): string {
  switch (tier.trim().toLowerCase()) {
    case "premium":
      return "高级会员";
    case "basic":
      return "基础会员";
    case "none":
    default:
      return "免费版";
  }
}

function avatarLetter(username: string | null): string {
  if (!username) return "";
  const t = username.trim();
  if (!t) return "";
  return t.slice(0, 1).toUpperCase();
}

export default function UserProfileMenu() {
  const { username, membershipTier, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocPointerDown = (e: PointerEvent) => {
      const el = rootRef.current;
      if (el && !el.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onDocPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDocPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const handleLogout = useCallback(() => {
    setOpen(false);
    void logout();
  }, [logout]);

  const letter = avatarLetter(username);

  return (
    <div className="relative shrink-0" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-gradient-to-br from-slate-700 to-slate-900 text-sm font-semibold text-white shadow-sm outline-none ring-offset-2 transition hover:from-slate-600 hover:to-slate-800 focus-visible:ring-2 focus-visible:ring-blue-500"
        title={username ?? "账户"}
      >
        {letter ? (
          <span aria-hidden>{letter}</span>
        ) : (
          <User className="h-4 w-4" aria-hidden />
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-60 rounded-xl border border-slate-200 bg-white py-2 shadow-xl"
        >
          <div className="border-b border-slate-100 px-4 pb-3 pt-1">
            <p className="truncate text-sm font-semibold text-slate-900">
              {username ?? "用户"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              会员等级：{membershipTierLabel(membershipTier)}
            </p>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <LogOut className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}
