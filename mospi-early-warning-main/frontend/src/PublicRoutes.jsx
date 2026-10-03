import { ArrowLeft, Lock } from "lucide-react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { useT } from "./hooks/useT";
import { PlatformDataProvider } from "./hooks/usePlatformData";
import { AppShell } from "./layout/AppShell";
import { PublicSessionProvider, usePublicSession } from "./PublicSession";
import PublicDirectory from "./PublicDirectory";
import { ReportIssuePage } from "./ReportIssuePage";
import { OptionsPage } from "./features/options/OptionsPage";
import {
  DashboardRoute,
  GraphRoute,
  IntelligenceRoute,
  MinistriesRoute,
  ProjectsRoute,
  ReportsRoute,
  StatesRoute,
} from "./routes/containers";

/**
 * Layout route for every public feature screen.
 *
 * `AppShell` renders an `Outlet`, so wrapping it here gives the feature routes
 * the project dialog and the shared page state the route containers read, with
 * `readOnly` set, which is what strips the write controls. `bare` drops the
 * console chrome — sidebar, topbar, banner, footer, palette, chat — so a nav
 * item opens that feature and nothing else. The data provider is required
 * because the shell reads the platform feed through it.
 */
function ReadOnlyLayout() {
  return (
    <PlatformDataProvider>
      <AppShell readOnly bare />
    </PlatformDataProvider>
  );
}

/** Shown where a route exists but its data is role-scoped. */
function SignInRequired() {
  const { onLogin } = usePublicSession();
  const t = useT();
  return (
    <div className="min-h-screen bg-page">
      <div className="border-b border-line bg-raised px-4 py-2.5 md:px-6">
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-fg-3 transition hover:bg-page hover:text-fg"
        >
          <ArrowLeft size={14} />
          {t("common.backToPortal")}
        </Link>
      </div>

      <div className="mx-auto max-w-lg px-4 py-20 text-center">
        <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-sunken text-fg-3">
          <Lock size={24} />
        </span>
        <h1 className="mt-5 text-xl font-extrabold uppercase tracking-tight text-fg">
          {t("signInRequired.title")}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-fg-3">
          {t("signInRequired.body")}
        </p>
        <button
          type="button"
          onClick={onLogin}
          className="mt-7 rounded-full bg-brand px-6 py-3 text-xs font-bold uppercase tracking-wider text-brand-fg transition hover:opacity-90"
        >
          {t("common.signIn")}
        </button>
        <p className="mt-4 text-[11px] uppercase tracking-wider text-fg-4">
          {t("signInRequired.note")}
        </p>
      </div>
    </div>
  );
}

/**
 * Route table for anonymous visitors and `viewer` accounts.
 *
 * The portal stays the home page at `/`; every analytical feature is a real
 * route beneath it so a URL can be shared or bookmarked. `/workspace` is the
 * one deliberate exception — it renders the sign-in notice rather than the
 * role panels, because those are the only screens whose data is not already
 * public.
 */
export function PublicRoutes({
  language,
  setLanguage,
  onLogin,
  loggedInUser,
  onLogout,
}) {
  const session = { language, setLanguage, onLogin, loggedInUser, onLogout, readOnly: true };

  return (
    <PublicSessionProvider value={session}>
      <Routes>
        <Route
          path="/"
          element={
            <PublicDirectory
              language={language}
              setLanguage={setLanguage}
              onLogin={onLogin}
              loggedInUser={loggedInUser}
              onLogout={onLogout}
            />
          }
        />

        <Route element={<ReadOnlyLayout />}>
          <Route path="dashboard" element={<DashboardRoute />} />
          <Route path="projects" element={<ProjectsRoute />} />
          <Route path="states" element={<StatesRoute />} />
          <Route path="ministries" element={<MinistriesRoute />} />
          <Route path="reports" element={<ReportsRoute />} />
          <Route path="graph" element={<GraphRoute />} />
          <Route path="options" element={<OptionsPage />} />
          <Route path=":lens" element={<IntelligenceRoute />} />
        </Route>

        {/* Top-level rather than under `ReadOnlyLayout`: this page brings its
            own public chrome, so wrapping it in AppShell would double the
            masthead and nav. */}
        <Route
          path="/report-an-issue"
          element={
            <ReportIssuePage
              language={language}
              setLanguage={setLanguage}
              onLogin={onLogin}
              loggedInUser={loggedInUser}
              onLogout={onLogout}
            />
          }
        />

        {/* Reachable only by typing the URL: the workspace is not public. */}
        <Route path="/workspace" element={<SignInRequired />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </PublicSessionProvider>
  );
}
