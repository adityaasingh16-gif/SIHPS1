/**
 * Route containers.
 *
 * Each page component was written to take `setActive`, `setSelectedProject`
 * and `projectsList` as props from a single parent. Rather than rewrite
 * every page during the routing change, these thin wrappers read that state
 * from the shell context and re-inject it in the shape each page expects.
 * The page components themselves are untouched.
 */
import { Navigate, useParams } from "react-router-dom";
import { lazy } from "react";

import { useAuth } from "../AuthContext";
import { useShellState } from "../layout/AppShell";

// Every page is lazy-loaded so heavy view libraries (maplibre for the state
// map, recharts for charts) are only downloaded when the page that uses them
// is actually opened. The bundler emits one chunk per route.
const DashboardHome = lazy(() => import("../features/dashboard/DashboardHome").then((m) => ({ default: m.DashboardHome })));
const ProjectsPage = lazy(() => import("../features/projects/ProjectsPage").then((m) => ({ default: m.ProjectsPage })));
const StatesPage = lazy(() => import("../features/states/StatesPage").then((m) => ({ default: m.StatesPage })));
const MinistriesPage = lazy(() => import("../features/ministries/MinistriesPage").then((m) => ({ default: m.MinistriesPage })));
const IntelligencePage = lazy(() => import("../features/intelligence/IntelligencePage").then((m) => ({ default: m.IntelligencePage })));
const ReportsPage = lazy(() => import("../features/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const MLStudioPage = lazy(() => import("../features/ml-studio/MLStudioPage").then((m) => ({ default: m.MLStudioPage })));
const KnowledgeGraph = lazy(() => import("../KnowledgeGraph"));
const AdminPanel = lazy(() => import("../AdminPanel"));
const MinistryPanel = lazy(() => import("../MinistryPanel"));
const AgencyPanel = lazy(() => import("../AgencyPanel"));

/** The valid `:lens` values, mirroring the sidebar's Intelligence group. */
const LENSES = ["risk", "cost", "time", "warnings"];

export function DashboardRoute() {
  const { projectsList, setSelectedProject, handleNavigate } = useShellState();
  return (
    <DashboardHome
      projectsList={projectsList}
      setSelectedProject={setSelectedProject}
      setActive={handleNavigate}
    />
  );
}

export function ProjectsRoute() {
  const { projectsList, search, setSearch, setSelectedProject } = useShellState();
  return (
    <ProjectsPage
      projectsList={projectsList}
      search={search}
      setSearch={setSearch}
      setSelectedProject={setSelectedProject}
    />
  );
}

export function StatesRoute() {
  const { setSearch, handleNavigate } = useShellState();
  return <StatesPage setSearch={setSearch} setActive={handleNavigate} />;
}

/**
 * `risk`, `cost`, `time` and `warnings` are four URLs that render one
 * component with a different lens. They were four sibling entries in the old
 * `active` state machine; keeping four paths means each stays linkable.
 */
export function IntelligenceRoute() {
  const { lens } = useParams();
  const { projectsList, setSelectedProject, handleNavigate } = useShellState();

  // The route is a catch-all, so guard the lens: an unknown path falls back
  // to the dashboard instead of rendering a page in a nonsense mode.
  if (!LENSES.includes(lens)) return <Navigate to="/" replace />;

  return (
    <IntelligencePage
      mode={lens}
      projectsList={projectsList}
      setSelectedProject={setSelectedProject}
      setActive={handleNavigate}
    />
  );
}

export function MinistriesRoute() {
  return <MinistriesPage />;
}

export function ReportsRoute() {
  const { projectsList } = useShellState();
  return <ReportsPage projectsList={projectsList} />;
}

export function MLStudioRoute() {
  const { projectsList, hasLiveData, selectedProject, setSelectedProject, handleNavigate, readOnly } =
    useShellState();
  return (
    <MLStudioPage
      projectsList={projectsList}
      hasLiveData={hasLiveData}
      selectedProject={selectedProject}
      setSelectedProject={setSelectedProject}
      setActive={handleNavigate}
      readOnly={readOnly}
    />
  );
}

export function GraphRoute() {
  const { setSelectedProject, handleNavigate } = useShellState();
  return (
    <KnowledgeGraph setSelectedProject={setSelectedProject} setActive={handleNavigate} />
  );
}

/**
 * The workspace is role-dependent, so the route resolves the panel.
 * Viewers never reach this route: the auth gate sends them to the public
 * directory before the router is mounted.
 */
export function WorkspaceRoute() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role === "admin") return <AdminPanel />;
  if (user.role === "ministry") return <MinistryPanel />;
  if (user.role === "agency") return <AgencyPanel />;
  return null;
}
