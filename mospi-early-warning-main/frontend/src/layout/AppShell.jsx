import { createContext, useCallback, useContext, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LogOut, ShieldCheck } from "lucide-react";
import { ArrowLeft } from "lucide-react";

import { useAuth } from "../AuthContext";
import { EnglishOnlyScope, useLanguage, useTheme } from "../hooks/usePreferences";
import { useT } from "../hooks/useT";
import { translate } from "../i18n";
import { usePlatformData } from "../hooks/usePlatformData";
import { usePublicSession } from "../PublicSession";
import { ProjectModal } from "../features/projects/ProjectModal";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { CommandPalette } from "../components/ui/CommandPalette";
import ChatWidget from "../ChatWidget";
import JarvisPopup from "../JarvisPopup";

/**
 * Role label for the sidebar footer. Takes the translator rather than reading
 * the locale itself so it stays in step with the rest of the shell chrome.
 */
const workspaceLabel = (role, t) =>
  ({
    admin: t("workspace.admin"),
    ministry: t("workspace.ministry"),
    agency: t("workspace.agency"),
    viewer: t("workspace.viewer"),
  })[role] ?? t("workspace.default");

/** Roles that get a dedicated, English-only operations panel at /workspace. */
const ROLE_WORKSPACE_ROLES = new Set(["admin", "ministry", "agency"]);

/**
 * Cross-cutting UI state that routes need to read or change: the search box,
 * the open project dialog, and navigation.
 *
 * The page components were written to receive these as props. Rather than
 * change every one of them during the routing move, the shell publishes them
 * here and the route containers inject them back in. That keeps this a pure
 * structural change.
 */
const ShellStateContext = createContext(null);

export function useShellState() {
  const ctx = useContext(ShellStateContext);
  if (!ctx) throw new Error("useShellState must be used inside <AppShell>");
  return ctx;
}

/**
 * Chrome for every authenticated surface: sidebar, topbar, the routed page,
 * and the overlays that sit above all of it.
 *
 * The project dialog lives here rather than in each page because it is
 * reachable from nearly every table and card; pages only need to raise
 * `setSelectedProject`.
 */
export function AppShell({ readOnly = false, bare = false }) {
  const { user, logout } = useAuth();
  const { dark, toggleTheme } = useTheme();
  const { language, setLanguage } = useLanguage();
  const activeT = useT();
  const englishT = useCallback((key, vars) => translate("en", key, vars), []);
  const { projectsList, hasLiveData, liveAlerts, backendStatus, isRefreshing, lastUpdated, refreshAll } =
    usePlatformData();
  // Present only on the public route table; `{}` in the console, so the
  // fallback below keeps the signed-in shell unchanged.
  const { onLogin: publicOnLogin } = usePublicSession();

  const navigate = useNavigate();
  const location = useLocation();

  // The role workspaces are English-only, so that whole surface is pinned to
  // English: the shell chrome matches the panel instead of framing it in a
  // different language. The stored preference is untouched, so the officer's
  // chosen language is still in force everywhere else.
  const activeSection =
    location.pathname.replace(/^\//, "").split("/")[0] || "dashboard";
  const isRoleWorkspace =
    activeSection === "workspace" && ROLE_WORKSPACE_ROLES.has(user?.role);
  const t = isRoleWorkspace ? englishT : activeT;

  // Admins get a panel-only console: no sidebar anywhere, so the workspace and
  // every console page render without the app nav rail.
  const hideSidebarFor = isRoleWorkspace || user?.role === "admin";

  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const closeProject = useCallback(() => setSelectedProject(null), []);
  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  // `active` used to be a single piece of state that every nav item wrote to.
  // Navigation now goes through the router, and the active item is derived
  // from the URL, so the two can never disagree.
  const handleNavigate = useCallback(
    (id) => {
      navigate(id === "dashboard" ? "/" : `/${id}`);
      setMobileNavOpen(false);
    },
    [navigate]
  );

  const shellState = {
    search,
    setSearch,
    selectedProject,
    setSelectedProject,
    navigate,
    handleNavigate,
    projectsList,
    // Lets a page tell the seeded demo rows apart from the real feed before
    // it issues any request keyed by project id.
    hasLiveData,
    // Read through the shell rather than threaded into each page's props, so
    // a page that renders a write control can drop it without the route
    // containers having to know which table they are mounted in.
    readOnly,
  };

  const shell = (
    <ShellStateContext.Provider value={shellState}>
      <div className="min-h-screen bg-page text-fg">
        <a href="#main-content" className="sr-only-focusable">
          {t("shell.skipMain")}
        </a>

        {!bare && !hideSidebarFor && (
          <Sidebar
            active={activeSection}
            setActive={handleNavigate}
            collapsed={collapsed}
            setCollapsed={setCollapsed}
            mobileOpen={mobileNavOpen}
            onCloseMobile={() => setMobileNavOpen(false)}
            user={user}
            onLogout={logout}
            language={isRoleWorkspace ? "en" : language}
            workspaceLabel={workspaceLabel(user?.role, t)}
          />
        )}

        <main
          id="main-content"
          tabIndex={-1}
          className={`transition-all ${bare || hideSidebarFor ? "" : collapsed ? "md:ml-[72px]" : "md:ml-[260px]"}`}
        >
          {/* `bare`/workspace pages carry no topbar, so this is the only way off them. */}
          {(bare || isRoleWorkspace) && (
            <div className="border-b border-line bg-raised px-4 py-2.5 md:px-6">
              {isRoleWorkspace && user?.role === "admin" ? (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-subtle text-brand">
                      <ShieldCheck size={18} />
                    </span>
                    <h2 className="text-sm font-bold text-fg">
                      {t("workspace.admin")}
                    </h2>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-[11px] font-bold uppercase text-brand-fg">
                      {(user.name || user.email || "?").slice(0, 1)}
                    </span>
                    <div className="hidden min-w-0 md:block">
                      <p className="truncate text-xs font-semibold text-fg">
                        {user.name || t("shell.userFallback")}
                      </p>
                      <p className="truncate text-[10px] capitalize text-fg-3">
                        {user.role}
                      </p>
                    </div>
                    <button
                      onClick={logout}
                      title={t("common.signOut")}
                      aria-label={t("common.signOut")}
                      className="rounded-lg p-2 text-fg-3 transition hover:bg-risk-critical-subtle hover:text-risk-critical"
                    >
                      <LogOut size={15} />
                    </button>
                  </div>
                </div>
              ) : (
                <Link
                  to="/"
                  className="inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-fg-3 transition hover:bg-page hover:text-fg"
                >
                  <ArrowLeft size={14} />
                  {t("common.backToPortal")}
                </Link>
              )}
            </div>
          )}

          {!bare && !isRoleWorkspace && (
            <>
              {/* Government trust bar: ministry identity, data provenance and
                  session freshness. Static chrome — no data logic changes. */}
              <div className="gov-gradient rise flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-1.5 text-[11px] text-white md:px-6">
                <p className="flex min-w-0 items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-amber-400 to-emerald-600 text-[7px] font-extrabold text-white"
                  >
                    IN
                  </span>
                  <span className="truncate font-semibold tracking-wide">
                    Government of India
                    <span className="mx-1.5 opacity-40">|</span>
                    <span className="font-normal opacity-90">
                      Ministry of Statistics &amp; Programme Implementation
                    </span>
                    <span className="mx-1.5 hidden opacity-40 sm:inline">|</span>
                    <span className="hidden font-normal opacity-70 sm:inline">
                      PAIMANA · SIH 26103
                    </span>
                  </span>
                </p>
                <p className="flex shrink-0 items-center gap-2">
                  <span
                    className={`inline-block h-1.5 w-1.5 rounded-full ${
                      backendStatus.online ? "animate-pulse bg-emerald-400" : "bg-amber-400"
                    }`}
                    aria-hidden="true"
                  />
                  <span className="font-semibold uppercase tracking-wider opacity-90">
                    {backendStatus.online ? t("shell.mlOnline") : t("shell.demoMode")}
                  </span>
                  <span className="opacity-60">
                    {t("common.lastSynced")}: {lastUpdated}
                  </span>
                </p>
              </div>
              <Topbar
                search={search}
                setSearch={setSearch}
                backendStatus={backendStatus}
                onRefresh={refreshAll}
                isRefreshing={isRefreshing}
                projectsList={projectsList}
                setSelectedProject={setSelectedProject}
                setActive={handleNavigate}
                liveAlerts={liveAlerts}
                onOpenMobile={user?.role === "admin" ? undefined : () => setMobileNavOpen(true)}
                dark={dark}
                onToggleDark={toggleTheme}
                language={isRoleWorkspace ? "en" : language}
                setLanguage={setLanguage}
                showLanguage={!isRoleWorkspace}
                onLogout={logout}
                showAccountChip={user?.role === "admin"}
              />

              {readOnly && (
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-sunken px-4 py-2 text-[11px] md:px-6">
                  <p className="font-semibold uppercase tracking-wider text-fg-3">
                    {t("shell.readOnlyBanner")}
                  </p>
                  {publicOnLogin && (
                    <button
                      type="button"
                      onClick={publicOnLogin}
                      className="rounded-full bg-brand px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-brand-fg transition hover:opacity-90"
                    >
                      {t("shell.signInFullAccess")}
                    </button>
                  )}
                </div>
              )}
            </>
          )}

          <div className="mx-auto max-w-[1700px] p-4 md:p-6">
            <Outlet />

            {!bare && (
              <footer className="mt-10 border-t border-line py-6 text-center text-xs text-fg-3">
                Dhrishti • SIH Problem Statement 26103 • ML Core: XGBoost +
                MLP-with-dropout + TreeSHAP + Platt Calibrator + OR-Tools MILP •
                Dhrishti Assistant: Groq generation with role-scoped retrieval
                <span className="mt-1 block">
                  {t("common.lastSynced")}: {lastUpdated}
                </span>
              </footer>
            )}
          </div>
        </main>

        {selectedProject && (
          <ProjectModal
            project={selectedProject}
            onClose={closeProject}
            readOnly={readOnly}
          />
        )}

        {!bare && (
          <CommandPalette
            open={paletteOpen}
            onOpen={openPalette}
            onClose={closePalette}
            projects={projectsList}
            onNavigate={handleNavigate}
            onSelectProject={setSelectedProject}
            onToggleTheme={toggleTheme}
            dark={dark}
            onLogout={logout}
          />
        )}

        {/* The assistants belong to the public surface: they are the only
            navigation an anonymous visitor has on a bare page, and the console
            already has the sidebar and palette for that. */}
        {bare && (
          <>
            <ChatWidget backendOnline={backendStatus.online} />
            <JarvisPopup backendOnline={backendStatus.online} setActive={handleNavigate} />
          </>
        )}
      </div>
    </ShellStateContext.Provider>
  );

  // `EnglishOnlyScope` re-provides the preferences context pinned to English,
  // which is what the sidebar, topbar and routed panel read through their own
  // `useT()` calls. AppShell's own strings use the `t` chosen above, so the two
  // agree.
  if (!isRoleWorkspace) return shell;
  return <EnglishOnlyScope>{shell}</EnglishOnlyScope>;
}
