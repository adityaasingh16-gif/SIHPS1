import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { fetchAuthMe } from "./api";

const AuthContext = createContext(null);
const TOKEN_KEY = "dhrishti-token";

function parseTokenFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return {
    token: params.get("token"),
    pending: params.get("pending") === "1",
    revoked: params.get("revoked") === "1",
    error: params.get("error"),
  };
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem(TOKEN_KEY) || null;
    } catch {
      return null;
    }
  });
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | authed | pending | revoked | anonymous
  const [bootError, setBootError] = useState(null);

  // On first load, pick up token from OAuth/demo redirect query params.
  useEffect(() => {
    const { token: urlToken, pending, revoked, error } = parseTokenFromUrl();
    if (urlToken) {
      try {
        localStorage.setItem(TOKEN_KEY, urlToken);
      } catch {
        /* ignore */
      }
      setToken(urlToken);
      if (pending) setStatus("pending");
      else if (revoked) setStatus("revoked");
      else if (error) setBootError(error);
    }
    // Clean the query string so refreshes don't replay the redirect.
    window.history.replaceState({}, document.title, window.location.pathname);
  }, []);

  // Resolve token -> user.
  useEffect(() => {
    if (!token) {
      setUser(null);
      setStatus("anonymous");
      return;
    }
    let mounted = true;
    setStatus("loading");
    fetchAuthMe(token)
      .then((res) => {
        if (!mounted) return;
        if (res?.authenticated) {
          setUser(res.user);
          setStatus("authed");
        } else if (res?.pending) {
          setUser(res.user);
          setStatus("pending");
        } else if (res?.user?.status === "revoked") {
          setUser(res.user);
          setStatus("revoked");
        } else {
          setUser(null);
          setStatus("anonymous");
        }
      })
      .catch((err) => {
        if (mounted) {
          console.warn("Auth bootstrap failed:", err);
          setStatus("anonymous");
        }
      });
    return () => {
      mounted = false;
    };
  }, [token]);

  const setAuthToken = (newToken, extra = {}) => {
    try {
      localStorage.setItem(TOKEN_KEY, newToken);
    } catch {
      /* ignore */
    }
    setToken(newToken);
    if (extra.pending) setStatus("pending");
  };

  const logout = () => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    setToken(null);
    setUser(null);
    setStatus("anonymous");
  };

  const completePasswordChange = (newUser) => {
    setUser(newUser);
  };

  const value = useMemo(
    () => ({
      token,
      user,
      status,
      bootError,
      mustChangePassword: user?.password_must_change === true,
      setAuthToken,
      logout,
      setBootError,
      completePasswordChange,
    }),
    [token, user, status, bootError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}