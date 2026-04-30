import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";

export interface AuthState {
  ready: boolean;
  /** True when at least one user account exists (bootstrap completed). */
  authEnabled: boolean;
  /** When true, unauthenticated clients cannot use protected API / app shell. */
  authRequired: boolean;
  needsBootstrap: boolean;
  authenticated: boolean;
  username: string | null;
  isAdmin: boolean;
  membershipTier: string;
  reportDailyLimit: number | null;
  reportUsedToday: number;
  valuationAllowed: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

type SessionPayload = {
  auth_enabled: boolean;
  auth_required: boolean;
  needs_bootstrap: boolean;
  authenticated: boolean;
  username: string | null;
  is_admin: boolean;
  membership_tier: string;
  report_daily_limit: number | null;
  report_used_today: number;
  valuation_allowed: boolean;
};

function applySessionPayload(
  j: SessionPayload,
  setters: {
    setAuthEnabled: (v: boolean) => void;
    setAuthRequired: (v: boolean) => void;
    setNeedsBootstrap: (v: boolean) => void;
    setAuthenticated: (v: boolean) => void;
    setUsername: (v: string | null) => void;
    setIsAdmin: (v: boolean) => void;
    setMembershipTier: (v: string) => void;
    setReportDailyLimit: (v: number | null) => void;
    setReportUsedToday: (v: number) => void;
    setValuationAllowed: (v: boolean) => void;
  },
) {
  setters.setAuthEnabled(j.auth_enabled);
  setters.setAuthRequired(Boolean(j.auth_required));
  setters.setNeedsBootstrap(j.needs_bootstrap);
  setters.setAuthenticated(j.authenticated);
  setters.setUsername(j.username);
  setters.setIsAdmin(Boolean(j.is_admin));
  setters.setMembershipTier(j.membership_tier ?? "none");
  setters.setReportDailyLimit(
    j.report_daily_limit === null || j.report_daily_limit === undefined
      ? null
      : Number(j.report_daily_limit),
  );
  setters.setReportUsedToday(Number(j.report_used_today ?? 0));
  setters.setValuationAllowed(Boolean(j.valuation_allowed));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);
  const [needsBootstrap, setNeedsBootstrap] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [membershipTier, setMembershipTier] = useState("none");
  const [reportDailyLimit, setReportDailyLimit] = useState<number | null>(10);
  const [reportUsedToday, setReportUsedToday] = useState(0);
  const [valuationAllowed, setValuationAllowed] = useState(false);
  const sessionFetchGeneration = useRef(0);

  const refresh = useCallback(async () => {
    const res = await apiFetch("/api/auth/session");
    if (!res.ok) {
      throw new Error(`session ${res.status}`);
    }
    const j = (await res.json()) as SessionPayload;
    applySessionPayload(j, {
      setAuthEnabled,
      setAuthRequired,
      setNeedsBootstrap,
      setAuthenticated,
      setUsername,
      setIsAdmin,
      setMembershipTier,
      setReportDailyLimit,
      setReportUsedToday,
      setValuationAllowed,
    });
  }, []);

  useEffect(() => {
    const gen = ++sessionFetchGeneration.current;
    const ac = new AbortController();
    const timeout = window.setTimeout(() => ac.abort(), 12000);

    void (async () => {
      try {
        const res = await apiFetch("/api/auth/session", {
          signal: ac.signal,
        });
        if (sessionFetchGeneration.current !== gen) {
          return;
        }
        if (!res.ok) {
          throw new Error(`session ${res.status}`);
        }
        const j = (await res.json()) as SessionPayload;
        applySessionPayload(j, {
          setAuthEnabled,
          setAuthRequired,
          setNeedsBootstrap,
          setAuthenticated,
          setUsername,
          setIsAdmin,
          setMembershipTier,
          setReportDailyLimit,
          setReportUsedToday,
          setValuationAllowed,
        });
      } catch {
        if (sessionFetchGeneration.current !== gen) {
          return;
        }
        setAuthEnabled(false);
        setAuthRequired(false);
        setNeedsBootstrap(false);
        setAuthenticated(false);
        setUsername(null);
        setIsAdmin(false);
        setMembershipTier("none");
        setReportDailyLimit(10);
        setReportUsedToday(0);
        setValuationAllowed(false);
      } finally {
        window.clearTimeout(timeout);
        if (sessionFetchGeneration.current === gen) {
          setReady(true);
        }
      }
    })();

    return () => {
      ac.abort();
    };
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      setAuthenticated(false);
      setUsername(null);
      setIsAdmin(false);
      navigate("/login", { replace: true });
    };
    window.addEventListener("app:unauthorized", onUnauthorized);
    return () => window.removeEventListener("app:unauthorized", onUnauthorized);
  }, [navigate]);

  const logout = useCallback(async () => {
    await apiFetch("/api/auth/logout", { method: "POST" });
    setAuthenticated(false);
    setUsername(null);
    setIsAdmin(false);
    let nextRequired = false;
    try {
      const res = await apiFetch("/api/auth/session");
      if (res.ok) {
        const j = (await res.json()) as SessionPayload;
        nextRequired = Boolean(j.auth_required);
        applySessionPayload(j, {
          setAuthEnabled,
          setAuthRequired,
          setNeedsBootstrap,
          setAuthenticated,
          setUsername,
          setIsAdmin,
          setMembershipTier,
          setReportDailyLimit,
          setReportUsedToday,
          setValuationAllowed,
        });
      }
    } catch {
      setMembershipTier("none");
      setReportDailyLimit(10);
      setReportUsedToday(0);
      setValuationAllowed(false);
    }
    navigate(nextRequired ? "/login" : "/", { replace: true });
  }, [navigate]);

  const value: AuthState = {
    ready,
    authEnabled,
    authRequired,
    needsBootstrap,
    authenticated,
    username,
    isAdmin,
    membershipTier,
    reportDailyLimit,
    reportUsedToday,
    valuationAllowed,
    refresh,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
