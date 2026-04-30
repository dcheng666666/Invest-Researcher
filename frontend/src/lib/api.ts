function requestPath(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    try {
      return new URL(input, window.location.origin).pathname;
    } catch {
      return input;
    }
  }
  if (input instanceof URL) {
    return input.pathname;
  }
  if (input instanceof Request) {
    try {
      return new URL(input.url).pathname;
    } catch {
      return input.url;
    }
  }
  return "";
}

/**
 * Same-origin fetch with session cookies. Dispatches ``app:unauthorized`` on 401
 * for protected API calls (not login).
 */
export function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const path = requestPath(input);
  return fetch(input, { ...init, credentials: "include" }).then((res) => {
    if (
      res.status === 401 &&
      path !== "/api/auth/login" &&
      path.startsWith("/api/")
    ) {
      window.dispatchEvent(new CustomEvent("app:unauthorized"));
    }
    return res;
  });
}
