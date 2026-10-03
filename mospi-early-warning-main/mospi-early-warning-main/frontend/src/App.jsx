import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { Route, Routes } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { useLanguage } from "./hooks/usePreferences";
import { PlatformDataProvider } from "./hooks/usePlatformData";
import { AppRoutes } from "./AppRoutes";
import { PublicRoutes } from "./PublicRoutes";
import PublicDirectory from "./PublicDirectory";
import LoginPage from "./LoginPage";
import ChangePasswordView from "./ChangePasswordView";

/**
 * Session gate.
 *
 * Decides which application the visitor gets before routing happens. The
 * router itself is mounted in `main.jsx`, above this gate, so both route
 * tables can be addressable.
 *
 * Two surfaces exist:
 *   - `AppRoutes`    — the operations console, for signed-in non-viewers.
 *   - `PublicRoutes` — the portal home plus every feature in read-only form,
 *                      for anonymous visitors and `viewer` accounts.
 *
 * `viewer` is a real account that is deliberately parked on the public
 * surface: it grants exactly the read-only access an anonymous visitor has,
 * so giving it the console would expose controls it cannot use.
 */
export default function App() {
  const { status, user, logout, mustChangePassword } = useAuth();
  const { language, setLanguage } = useLanguage();
  const [loginOpen, setLoginOpen] = useState(false);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-page">
        <div className="flex items-center gap-3 text-sm text-fg-4">
          <RefreshCw className="h-5 w-5 animate-spin text-brand" />
          Verifying session…
        </div>
      </div>
    );
  }

  if (mustChangePassword) {
    return <ChangePasswordView language={language} setLanguage={setLanguage} />;
  }

  if (status !== "authed" || user?.role === "viewer") {
    if (loginOpen) {
      return (
        <LoginPage
          language={language}
          setLanguage={setLanguage}
          onBackBrowse={() => setLoginOpen(false)}
        />
      );
    }
    return (
      <PublicRoutes
        language={language}
        setLanguage={setLanguage}
        onLogin={() => setLoginOpen(true)}
        loggedInUser={user}
        onLogout={logout}
      />
    );
  }

  return (
    <Routes>
      {/* The hero portal is the landing for EVERYONE, signed in or not: the
          root URL opens the public directory. Signed-in officers reach the
          console from the portal nav / its links. */}
      <Route
        path="/"
        element={
          <PublicDirectory
            language={language}
            setLanguage={setLanguage}
            onLogin={() => setLoginOpen(true)}
            loggedInUser={user}
            onLogout={logout}
          />
        }
      />
      <Route
        path="*"
        element={
          <PlatformDataProvider>
            <AppRoutes />
          </PlatformDataProvider>
        }
      />
    </Routes>
  );
}
