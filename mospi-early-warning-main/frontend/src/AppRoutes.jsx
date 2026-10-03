import { Navigate, Route, Routes } from "react-router-dom";
import { Suspense } from "react";

import { AppShell } from "./layout/AppShell";
import { useAuth } from "./AuthContext";
import {
  DashboardRoute,
  GraphRoute,
  IntelligenceRoute,
  MinistriesRoute,
  ProjectsRoute,
  ReportsRoute,
  StatesRoute,
  WorkspaceRoute,
} from "./routes/containers";

// Admins live in the Admin Control Center: "/" is their home, not the
// console dashboard. Everyone else keeps the console landing page.
function AdminLanding() {
  const { user } = useAuth();
  if (user?.role === "admin") return <Navigate to="/workspace" replace />;
  return <DashboardRoute />;
}

/**
 * Route table for authenticated surfaces.
 *
 * Every screen is now addressable, so a URL can be shared, bookmarked or
 * reached with the browser's back button. The previous `active` state
 * machine could do none of that, and the active nav item could disagree with
 * what was on screen.
 */
export function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[60vh] items-center justify-center text-sm text-fg-3">
          Loading…
        </div>
      }
    >
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<AdminLanding />} />
          <Route path="projects" element={<ProjectsRoute />} />
          <Route path="states" element={<StatesRoute />} />
          <Route path="ministries" element={<MinistriesRoute />} />
          <Route path="reports" element={<ReportsRoute />} />
          <Route path="graph" element={<GraphRoute />} />
          <Route path="workspace" element={<WorkspaceRoute />} />
          <Route path=":lens" element={<IntelligenceRoute />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
