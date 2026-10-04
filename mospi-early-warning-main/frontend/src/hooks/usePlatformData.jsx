import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { checkBackendHealth, fetchAlerts, fetchProjects } from "../api";
import { alerts as seedAlerts, projects as seedProjects } from "../data";

const PlatformDataContext = createContext(null);

/** Auto-refresh cadence for the shared project/alerts snapshot. */
const REFRESH_MS = 300000;

/**
 * Owns the platform-wide data snapshot: backend health, the project list and
 * the early-warning queue.
 *
 * This previously lived inside the App component, so every surface received
 * its data as props drilled down from one place and each new route had to be
 * threaded through that chain. Hoisting it into a provider gives any route
 * access and puts loading/error ownership in a single file.
 *
 * Seed data stays as the initial value so a slow or unreachable API still
 * renders a usable screen; `getDataSource()` in the api layer is what tells
 * the UI whether it is looking at live or demo figures.
 */
export function PlatformDataProvider({ children }) {
  const location = useLocation();
  const isRoleWorkspace = location.pathname.replace(/\/+$/, "") === "/workspace";
  const [projectsList, setProjectsList] = useState(seedProjects);
  const [liveAlerts, setLiveAlerts] = useState(seedAlerts);
  const [backendStatus, setBackendStatus] = useState({
    online: false,
    modelsLoaded: false,
    platform: "Connecting...",
    version: "1.0.0",
  });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [syncError, setSyncError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(() => new Date().toLocaleString());
  // Distinguishes "the seed snapshot" from "the real feed". The list is seeded
  // so a slow API still paints something, which means a non-empty
  // `projectsList` cannot be trusted as proof the ids are real: seed rows use
  // ids like PRJ_006 that the database has never heard of, and any per-id
  // request against one 404s. Pages that fetch by id must wait for this.
  const [hasLiveData, setHasLiveData] = useState(false);

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    try {
      setBackendStatus(await checkBackendHealth());

      // Role workspace panels load their own scoped data. Pulling the full
      // portfolio and alert feed here adds unrelated MongoDB work to every
      // Admin, Ministry, and Agency login.
      if (isRoleWorkspace) {
        setLastUpdated(new Date().toLocaleString());
        setSyncError(null);
        return;
      }

      const projectData = await fetchProjects();
      if (projectData && projectData.length > 0) {
        setProjectsList(projectData);
        setHasLiveData(true);
      }

      const alertData = await fetchAlerts();
      if (alertData && alertData.length > 0) setLiveAlerts(alertData);

      setLastUpdated(new Date().toLocaleString());
      setSyncError(null);
    } catch (err) {
      // A failed sync is not fatal: the seed snapshot stays on screen and the
      // topbar already surfaces the offline state.
      console.warn("Could not sync with backend:", err);
      setSyncError(err);
    } finally {
      setIsRefreshing(false);
    }
  }, [isRoleWorkspace]);

  useEffect(() => {
    let stop = false;
    // A page that loads while a deploy is mid-flight (or the instance is
    // cold-starting) can see a transient offline blip. Retry a few times with
    // a short pause instead of sitting on "offline" until the next 5-min sync.
    (async () => {
      for (let attempt = 0; attempt < 6 && !stop; attempt++) {
        const status = await checkBackendHealth();
        if (!stop) setBackendStatus(status);
        if (status.online) {
          // Health alone is not "live data": the list needs a real pull before
          // the UI can drop the sample-data banner. Fetch it now instead of
          // waiting for the 5-minute interval.
          if (!isRoleWorkspace) await refreshAll();
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 4000));
      }
    })();
    const timer = setInterval(refreshAll, REFRESH_MS);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [refreshAll, isRoleWorkspace]);

  const value = {
    projectsList,
    hasLiveData,
    liveAlerts,
    backendStatus,
    isRefreshing,
    syncError,
    lastUpdated,
    refreshAll,
  };

  return (
    <PlatformDataContext.Provider value={value}>
      {children}
    </PlatformDataContext.Provider>
  );
}

/**
 * Access the platform snapshot. Throws if used outside the provider, which
 * turns a confusing "undefined is not a function" into a precise message.
 */
export function usePlatformData() {
  const ctx = useContext(PlatformDataContext);
  if (!ctx) {
    throw new Error("usePlatformData must be used inside <PlatformDataProvider>");
  }
  return ctx;
}
