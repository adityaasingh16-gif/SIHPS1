import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { AlertTriangle, ArrowUpRight, Bell, Globe2, LogOut, Menu, Moon, RefreshCw, Search, ShieldCheck, Sun, X } from "lucide-react";
import { projects, alerts } from "../data";

import { LANGUAGES } from "../i18n";
import { useT } from "../hooks/useT";
import { RiskBadge } from "../components/ui/RiskBadge";

export { Topbar };

function Topbar({
  search ="",
  setSearch,
  backendStatus = { online: false },
  onRefresh,
  isRefreshing,
  projectsList = [],
  setSelectedProject,
  setActive,
  liveAlerts = [],
   onOpenMobile,
  dark = false,
  onToggleDark,
  language ="en",
  setLanguage,
  // The role workspaces are English-only, so the picker is hidden there rather
  // than offering a switch that would have no visible effect.
  showLanguage = true,
  onLogout,
  showAccountChip = false,
}) {
  const t = useT();
  const [showNotifications, setShowNotifications] = useState(false);
 const [notificationFilter, setNotificationFilter] = useState("all");
 const [showSearchDropdown, setShowSearchDropdown] = useState(false);
 const searchInputRef = useRef(null);
  const notificationButtonRef = useRef(null);

  // Month names are locale data, not strings to translate, so the snapshot
  // date is formatted through Intl rather than looked up in the catalogue.
  const snapshotLabel = useMemo(
    () =>
      new Intl.DateTimeFormat(language, {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date("2026-04-01T00:00:00Z")),
    [language]
  );

 // Escape closes whichever popover is open and returns focus to its trigger,
 // so keyboard users are never stranded inside an overlay.
 useEffect(() => {
 if (!showNotifications && !showSearchDropdown) return;

 function onKeyDown(e) {
 if (e.key !=="Escape") return;
 if (showSearchDropdown) {
 setShowSearchDropdown(false);
 searchInputRef.current?.focus();
 } else {
 setShowNotifications(false);
 notificationButtonRef.current?.focus();
 }
 }

 document.addEventListener("keydown", onKeyDown);
 return () => document.removeEventListener("keydown", onKeyDown);
 }, [showNotifications, showSearchDropdown]);

 // Opening one popover dismisses the other.
 const toggleNotifications = useCallback(() => {
 setShowSearchDropdown(false);
 setShowNotifications((open) => !open);
 }, []);

 const focusSearch = useCallback(() => {
 setShowNotifications(false);
 setShowSearchDropdown(true);
 }, []);

 // Search matches across projects
 const searchResults = useMemo(() => {
 if (!search || !search.trim()) return [];
 const q = search.toLowerCase().trim();
 const list = projectsList.length > 0 ? projectsList : projects;
 return list
 .filter((p) => {
 const idMatch = p.id && p.id.toLowerCase().includes(q);
 const nameMatch = p.name && p.name.toLowerCase().includes(q);
 const sectorMatch = p.sector && p.sector.toLowerCase().includes(q);
 const orgMatch =
 p.organization && p.organization.toLowerCase().includes(q);
 const minMatch = p.ministry && p.ministry.toLowerCase().includes(q);
 return idMatch || nameMatch || sectorMatch || orgMatch || minMatch;
 })
 .slice(0, 6);
 }, [search, projectsList]);

 // Filtered notifications
 const alertsSource = liveAlerts.length > 0 ? liveAlerts : alerts;
 const filteredAlerts = useMemo(() => {
 if (notificationFilter ==="critical") {
 return alertsSource.filter((a) => a.severity ==="Critical");
 }
 if (notificationFilter ==="high") {
 return alertsSource.filter((a) => a.severity ==="High");
 }
 return alertsSource;
 }, [alertsSource, notificationFilter]);

 const criticalCount = useMemo(
 () => alertsSource.filter((a) => a.severity ==="Critical").length,
 [alertsSource]
 );
 const highCount = useMemo(
 () => alertsSource.filter((a) => a.severity ==="High").length,
 [alertsSource]
 );

 const handleSelectProjectFromSearch = (proj) => {
 if (setSelectedProject) setSelectedProject(proj);
 setShowSearchDropdown(false);
 };

 const handleViewAllSearchResults = () => {
 if (setActive) setActive("projects");
 setShowSearchDropdown(false);
 };

 return (
 <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-line bg-raised/95 px-4 backdrop-blur md:px-6">
 <div className="flex min-w-0 items-center gap-3">
{onOpenMobile && (
   <button
   onClick={onOpenMobile}
    aria-label={t("shell.openNavMenu")}
    title={t("shell.openNavMenu")}
   className="rounded-xl border border-line p-2.5 text-fg-2 transition hover:bg-page md:hidden"
   >
   <Menu size={18} />
   </button>
  )}

  <div className="min-w-0">
 <p className="hidden truncate text-xs font-medium text-fg-4 md:block">
 {t("shell.mospiBlock")}
 </p>
 <h1 className="truncate text-base font-bold text-fg md:text-xl">
 {t("shell.infraBlock")}
 </h1>
 </div>
 </div>

  {/* Controls hold their size; the title beside them is what truncates. Letting
      this group shrink is worse than useless: its children are all shrink-0,
      so the row compresses and the children spill out past the viewport. */}
  <div className="flex shrink-0 items-center gap-2 md:gap-3">
 {/* ML Backend Status Pill */}
  {/* ML Backend Status Pill. The sidebar is a fixed 260px from md up, so the
      main column cannot carry the pill alongside the language, theme and
      notification controls until lg. The topbar is not the place to read
      backend health. */}
  <div className="hidden shrink-0 items-center gap-2 rounded-xl border border-line bg-page px-2 py-1.5 text-xs md:px-3 lg:flex">
 <span
 className={`h-2.5 w-2.5 rounded-full ${
 backendStatus.online
 ?"bg-risk-low shadow-sm shadow-risk-low/50 animate-pulse"
 :"bg-risk-medium"
 }`}
 />
  <span className="hidden font-medium text-fg-2 xl:inline">
 {backendStatus.online
 ?t("shell.mlOnline")
 :t("shell.demoMode")}
 </span>
 <button
 onClick={onRefresh}
 title={t("shell.resyncTitle")}
 aria-label={t("shell.resync")}
 className="ml-1 text-fg-4 transition hover:text-brand"
 >
 <RefreshCw
 size={13}
 className={isRefreshing ?"animate-spin text-brand" :""}
 />
 </button>
 </div>

  {/* Language Selector */}
   {showLanguage && (
   <label
  title={t("common.language")}
  className="flex min-w-0 shrink-0 items-center gap-2 rounded-xl border border-line px-2 py-2 text-fg-2 transition md:px-3"
  >
  <Globe2 size={17} className="shrink-0 text-fg-4" />
  <select
  value={language}
  onChange={(e) => setLanguage && setLanguage(e.target.value)}
  // Intrinsic width comes from the longest native name ("অসমীয়া"), which
  // pushed the row past the viewport on phones. Cap it per breakpoint.
  className="w-16 bg-transparent text-xs font-medium text-fg-2 outline-none sm:w-20 lg:max-w-[90px]"
  aria-label={t("shell.interfaceLanguage")}
 >
 {LANGUAGES.map((l) => (
 <option key={l.code} value={l.code}>
 {l.native}
 </option>
  ))}
  </select>
  </label>
  )}

 {/* Theme Toggle */}
 <button
 onClick={onToggleDark}
  aria-label={dark ?t("shell.lightMode") :t("shell.darkMode")}
  title={dark ?t("shell.lightMode") :t("shell.darkMode")}
  className="shrink-0 rounded-xl border border-line p-3 text-fg-2 transition hover:bg-page hover:text-brand :bg-fg md:p-2.5"
 >
 {dark ? <Sun size={18} /> : <Moon size={18} />}
 </button>

 {/* Global Search Bar with Live Results Dropdown */}
  <div className="relative min-w-0">
  {/* Search waits until lg. The sidebar is a fixed 236px, so below lg the main
      column cannot fit the search plus the status/language/theme/bell controls,
      and the row spills past the viewport instead of truncating. */}
  <div className="hidden items-center gap-2 rounded-xl border border-line bg-sunken px-3 py-2 transition focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/20 xl:flex">
 <Search size={17} className="shrink-0 text-fg-3" />
 <input
 ref={searchInputRef}
 value={search}
 onChange={(e) => {
 if (setSearch) setSearch(e.target.value);
 setShowSearchDropdown(true);
 }}
 onFocus={focusSearch}
 onKeyDown={(e) => {
 if (e.key ==="Enter") {
 handleViewAllSearchResults();
 }
 }}
  placeholder={t("shell.searchPlaceholder")}
 role="combobox"
 aria-expanded={showSearchDropdown}
 aria-controls="search-results"
 aria-autocomplete="list"
  className="w-40 bg-transparent text-sm text-fg outline-none placeholder:text-fg-3 lg:w-56"
 />
 {search && (
 <button
 onClick={() => {
 if (setSearch) setSearch("");
 setShowSearchDropdown(false);
 }}
   aria-label={t("shell.clearSearch")}
 className="text-fg-3 hover:text-fg"
 >
 <X size={14} />
 </button>
 )}
 </div>

 {/* Search Results Dropdown Popup */}
 {showSearchDropdown && search.trim() && (
 <>
 <div
 className="fixed inset-0 z-40"
 onClick={() => setShowSearchDropdown(false)}
 />
 <div
 id="search-results"
 role="listbox"
 className="absolute left-0 top-12 z-50 w-96 rounded-2xl border border-line bg-overlay p-3 shadow-pop"
 >
 <div className="mb-2 flex items-center justify-between border-b border-line px-2 pb-2 text-[11px] font-semibold uppercase text-fg-3">
 <span>{t("shell.matchingProjects", { q: search })}</span>
 <span className="text-brand">
 {t("shell.foundCount", { n: searchResults.length })}
 </span>
 </div>

 {searchResults.length > 0 ? (
 <div className="max-h-72 space-y-1.5 overflow-y-auto">
 {searchResults.map((p) => (
 <button
 key={p.id}
 role="option"
 aria-selected="false"
 onClick={() => handleSelectProjectFromSearch(p)}
 className="w-full rounded-xl p-2.5 text-left transition hover:bg-hover"
 >
 <div className="flex items-center justify-between">
 <span className="rounded-md bg-brand-subtle px-2 py-0.5 text-[10px] font-bold uppercase text-brand-subtle-fg">
 {p.id} • {p.sector}
 </span>
 <RiskBadge risk={p.risk} />
 </div>
 <p className="mt-1 line-clamp-1 text-xs font-bold text-fg">
 {p.name}
 </p>
 <p className="line-clamp-1 text-[11px] text-fg-3">
 {p.organization}
 </p>
 </button>
 ))}
 </div>
 ) : (
 <div className="py-6 text-center text-xs text-fg-3">
 {t("shell.noProjectsFound", { q: search })}
 </div>
 )}

 <div className="mt-2 border-t border-line pt-2">
 <button
 onClick={handleViewAllSearchResults}
 className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand-subtle py-2 text-xs font-semibold text-brand-subtle-fg transition hover:brightness-95"
 >
 {t("shell.viewInExplorer")}
 </button>
 </div>
 </div>
 </>
 )}
 </div>

 {/* Functional Notification Portal / Risk Alert Pop-up */}
 <div className="relative">
 <button
 ref={notificationButtonRef}
 onClick={toggleNotifications}
   title={t("shell.riskNotifications")}
   aria-label={`${t("shell.riskAlerts")}${
  criticalCount > 0 ?t("shell.criticalCountSuffix", { n: criticalCount }) :""
  }`}
 aria-expanded={showNotifications}
 aria-haspopup="dialog"
  className={`relative shrink-0 rounded-xl border p-2.5 transition md:p-3 ${
 showNotifications
 ?"border-brand bg-brand-subtle text-brand-subtle-fg"
 :"border-line text-fg-2 hover:bg-hover"
 }`}
 >
 <Bell size={18} />
 {alertsSource.length > 0 && (
 <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-risk-critical text-[10px] font-bold text-white ring-2 ring-brand">
 {alertsSource.length}
 </span>
 )}
 </button>

 {showNotifications && (
 <>
 <div
 className="fixed inset-0 z-40"
 onClick={() => setShowNotifications(false)}
 />
 <div
 role="dialog"
   aria-label={t("shell.riskAlerts")}
 className="absolute right-0 top-14 z-50 max-w-[92vw] w-[420px] rounded-2xl border border-line bg-overlay p-5 shadow-pop"
 >
 <div className="flex items-center justify-between border-b border-line pb-3">
 <div className="flex items-center gap-2">
 <div className="rounded-lg bg-risk-critical-subtle p-1.5 text-risk-critical">
 <AlertTriangle size={17} />
 </div>
 <div>
 <h3 className="text-sm font-bold text-fg">
 {t("shell.riskAlertsTitle")}
 </h3>
 <p className="text-[11px] text-fg-3">
 {t("shell.activeSignals", { n: alertsSource.length })}
 </p>
 </div>
 </div>

 <button
 onClick={() => setShowNotifications(false)}
   aria-label={t("shell.closeNotifications")}
 className="rounded-lg p-1 text-fg-3 hover:bg-hover hover:text-fg"
 >
 <X size={16} />
 </button>
 </div>

 {/* Filter chips */}
 <div className="mt-3 flex gap-1.5">
 <button
 onClick={() => setNotificationFilter("all")}
 className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
 notificationFilter ==="all"
 ?"bg-fg text-white"
 :"bg-sunken text-fg-2 hover:bg-hover"
 }`}
 >
 {t("common.all")} ({alertsSource.length})
 </button>
 <button
 onClick={() => setNotificationFilter("critical")}
 className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
 notificationFilter ==="critical"
 ?"bg-risk-critical text-white"
 :"bg-risk-critical-subtle text-risk-critical hover:bg-risk-critical-subtle"
 }`}
 >
 {t("common.critical")} ({criticalCount})
 </button>
 <button
 onClick={() => setNotificationFilter("high")}
 className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
 notificationFilter ==="high"
 ?"bg-risk-high text-white"
 :"bg-risk-high-subtle text-risk-high hover:bg-risk-high-subtle"
 }`}
 >
 {t("common.high")} ({highCount})
 </button>
 </div>

 {/* Alerts List */}
 <div className="mt-3 max-h-80 space-y-2.5 overflow-y-auto pr-1">
 {filteredAlerts.length > 0 ? (
 filteredAlerts.map((alert) => (
 <div
 key={alert.id}
 className="rounded-2xl border border-line bg-page/80 p-3.5 transition hover:bg-sunken/70 hover:shadow-sm"
 >
 <div className="flex items-start justify-between gap-2">
 <div>
 <span className="text-[10px] font-bold uppercase tracking-wider text-fg-4">
 {alert.type ||t("shell.trajectoryAlert")}
 </span>
 <p className="mt-0.5 text-xs font-bold text-fg">
 {alert.project}
 </p>
 </div>
 <RiskBadge
 risk={
 alert.score ??
 (alert.severity ==="Critical" ? 90 : 65)
 }
 />
 </div>
 <p className="mt-1.5 text-xs leading-relaxed text-fg-2">
 {alert.message}
 </p>
 <button
 onClick={() => {
 const list =
 projectsList.length > 0 ? projectsList : projects;
 const matched = list.find(
 (p) =>
 p.id === alert.project ||
 alert.message?.includes(p.id) ||
 p.name?.includes(alert.project)
 );
  if (matched && setSelectedProject) {
  setSelectedProject(matched);
  }
  setShowNotifications(false);
  }}
  className="mt-2.5 flex items-center gap-1 text-[11px] font-bold text-brand-hover hover:text-brand-active"
  >
  {t("common.openProject")} <ArrowUpRight size={13} />
 </button>
 </div>
 ))
 ) : (
 <div className="py-8 text-center text-xs text-fg-4">
 {t("shell.noNotifications")}
 </div>
 )}
 </div>

 <div className="mt-3 border-t border-line pt-3">
 <button
 onClick={() => {
 if (setActive) setActive("warnings");
 setShowNotifications(false);
 }}
 className="w-full rounded-xl bg-fg py-2.5 text-center text-xs font-bold text-white transition hover:bg-fg"
 >
 {t("shell.openWarningCenter")}
 </button>
 </div>
 </div>
 </>
 )}
 </div>

  {showAccountChip && (
   <div className="flex shrink-0 items-center gap-1.5 md:gap-2">
   <button
   onClick={() => setActive && setActive("workspace")}
    title={t("workspace.admin")}
    aria-label={t("workspace.admin")}
   className="rounded-xl border border-line p-2.5 text-fg-2 transition hover:bg-page hover:text-brand md:p-3"
   >
   <ShieldCheck size={16} />
   </button>
   <button
   onClick={onLogout}
    title={t("common.signOut")}
    aria-label={t("common.signOut")}
   className="rounded-xl border border-line p-2.5 text-fg-2 transition hover:bg-risk-critical-subtle hover:text-risk-critical md:p-3"
   >
   <LogOut size={16} />
   </button>
   </div>
  )}

   <div className="hidden rounded-xl bg-brand-subtle px-4 py-2 text-right xl:block">
 <p className="text-xs font-semibold text-brand-hover">{t("shell.dataSnapshot")}</p>
  <p className="text-[10px] text-brand">{snapshotLabel}</p>
 </div>
 </div>
 </header>
 );
}
