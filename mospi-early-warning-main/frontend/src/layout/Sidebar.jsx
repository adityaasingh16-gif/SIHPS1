import { Bell, Building2, ChevronRight, CircleDollarSign, Clock3, FileText, Gauge, Home, LogOut, Map as MapIcon, Menu, Network, ShieldCheck, Target, X } from "lucide-react";

import { languageLabel } from "../i18n";
import { useT } from "../hooks/useT";
import { DhrishtiGlyph, DhrishtiMark } from "../components/public/PublicChrome";

export { Sidebar };

function Sidebar({ active, setActive, collapsed, setCollapsed, mobileOpen, onCloseMobile, user, onLogout, language, workspaceLabel }) {
  const t = useT();
  // Each group carries its own hue so the nav reads as four distinct
  // areas rather than one flat list. Class names are written out in full
  // instead of interpolated, because Tailwind's scanner only sees literal
  // strings - `bg-${hue}` would compile to nothing.
  const HUE = {
  monitor: {
  marker: "bg-group-monitor",
  active: "bg-group-monitor-subtle text-group-monitor-subtle-fg",
  accent: "text-group-monitor",
  badge: "bg-group-monitor-subtle text-group-monitor-subtle-fg",
  edge: "border-l-group-monitor",
  },
  intelligence: {
  marker: "bg-group-intelligence",
  active: "bg-group-intelligence-subtle text-group-intelligence-subtle-fg",
  accent: "text-group-intelligence",
  badge: "bg-group-intelligence-subtle text-group-intelligence-subtle-fg",
  edge: "border-l-group-intelligence",
  },
  portfolio: {
  marker: "bg-group-portfolio",
  active: "bg-group-portfolio-subtle text-group-portfolio-subtle-fg",
  accent: "text-group-portfolio",
  badge: "bg-group-portfolio-subtle text-group-portfolio-subtle-fg",
  edge: "border-l-group-portfolio",
  },
  build: {
  marker: "bg-group-build",
  active: "bg-group-build-subtle text-group-build-subtle-fg",
  accent: "text-group-build",
  badge: "bg-group-build-subtle text-group-build-subtle-fg",
  edge: "border-l-group-build",
  },
  };

  // `risk`, `cost`, `time` and `warnings` all render the same IntelligencePage
  // with a different `mode`, so they are one destination with four lenses —
  // not four sibling destinations.
  const groups = [
  {
  label:t("shell.nav.monitor"),
  hue:HUE.monitor,
  items: [
  { id:"dashboard", label:t("shell.nav.dashboard"), icon: Home },
  { id:"warnings", label:t("shell.nav.earlyWarnings"), icon: Bell },
  ],
  },
  {
  label:t("shell.nav.intelligence"),
  hue:HUE.intelligence,
  items: [
  { id:"risk", label:t("shell.nav.riskAnalytics"), icon: Gauge },
  { id:"cost", label:t("shell.nav.costIntelligence"), icon: CircleDollarSign },
  { id:"time", label:t("shell.nav.timeIntelligence"), icon: Clock3 },
  ],
  },
  {
  label:t("shell.nav.portfolio"),
  hue:HUE.portfolio,
  items: [
  { id:"projects", label:t("shell.nav.highValue"), icon: Target },
  { id:"states", label:t("shell.nav.stateWise"), icon: MapIcon },
  { id:"ministries", label:t("shell.nav.ministries"), icon: Building2 },
  ],
  },
  {
  label:t("shell.nav.build"),
  hue:HUE.build,
  items: [
  { id:"graph", label:t("shell.nav.knowledgeGraph"), icon: Network },
  { id:"reports", label:t("shell.nav.reports"), icon: FileText },
  ],
  },
  ];

  // The workspace is the primary surface for every non-viewer role, so it
  // leads the nav instead of trailing it as a role-gated afterthought.
  const workspaceItem =
  user && user.role !=="viewer"
  ? [
  {
  label:t("shell.nav.workspace"),
  hue:HUE.monitor,
  items: [
  {
  id:"workspace",
  label: workspaceLabel ||t("workspace.default"),
  icon: ShieldCheck,
  badge: user.role,
  },
  ],
  },
  ]
  : [];

 return (
 <aside
 className={`fixed left-0 top-0 z-50 h-screen w-[260px] border-r border-line bg-raised transition-transform duration-300 ease-in-out md:z-40 md:transition-all ${
 collapsed ?"md:w-[72px]" :"md:w-[260px]"
 } ${mobileOpen ?"translate-x-0" :"-translate-x-full md:translate-x-0"}`}
  aria-label={t("common.primaryNav")}
 >
  <div className="flex h-full flex-col">
  <div className="flex h-16 shrink-0 items-center justify-between border-b border-line px-4">
  {/* The mark doubles as the collapse affordance's neighbour, so when the
      sidebar is collapsed only the glyph is shown — matching the 72px rail. */}
  {collapsed ? (
  <span className="flex h-8 w-8 items-center justify-center" title="Dhrishti">
  <DhrishtiGlyph className="h-7 w-7" />
  </span>
  ) : (
  <DhrishtiMark className="h-8" t={t} />
  )}


 <button
 onClick={() => {
 if (window.innerWidth < 768) {
 if (onCloseMobile) onCloseMobile();
 } else {
 setCollapsed(!collapsed);
 }
 }}
  aria-label={
  window.innerWidth < 768 ?t("shell.closeNavMenu") :t("shell.toggleSidebarWidth")
  }
 className="flex items-center gap-1.5 rounded-lg p-2 text-fg-3 transition hover:bg-hover hover:text-fg"
 >
 <X size={18} className="md:hidden" />
 {/* The drawer no longer sits on a dismiss-on-tap backdrop, so the close
     affordance has to be explicit rather than a bare icon. */}
  <span className="text-[11px] font-bold uppercase tracking-wider md:hidden">{t("common.close")}</span>
 <Menu size={18} className="hidden md:block" />
 </button>
 </div>

  <nav className="flex-1 overflow-y-auto overflow-x-hidden p-3">
  <div className="space-y-5">
  {[...workspaceItem, ...groups].map((group) => (
  <div key={group.label}>
  {!collapsed && (
  <p className="flex items-center gap-2 px-3 pb-1.5 text-[10px] font-bold uppercase tracking-widest text-fg-3">
  {/* Hue marker: the only place a group is identified by colour, so the
      nav stays scannable without tinting every row. */}
  <span
  className={`h-1.5 w-1.5 shrink-0 rounded-full ${group.hue.marker}`}
  aria-hidden="true"
  />
  {group.label}
  </p>
  )}

  <ul className="space-y-0.5">
  {group.items.map((item) => {
  const Icon = item.icon;
  const selected = active === item.id;

  return (
  <li key={item.id}>
  <button
  onClick={() => setActive(item.id)}
  aria-current={selected ?"page" : undefined}
  title={collapsed ? item.label : undefined}
  className={`group relative flex w-full items-center gap-3 rounded-lg border-l-2 py-2 pl-2.5 pr-3 text-left text-sm transition ${
  selected
  ? `font-semibold ${group.hue.active} ${group.hue.edge}`
  : "border-l-transparent text-fg-2 hover:bg-hover hover:text-fg"
  }`}
  >
  <Icon
  size={17}
  className={`shrink-0 ${selected ? group.hue.accent : ""}`}
  />

  {!collapsed && (
  <>
  <span className="flex-1 truncate">{item.label}</span>

  {item.badge && (
  <span
  className={`rounded-full px-2 py-0.5 text-[9px] font-extrabold uppercase ${
  selected ? group.hue.badge : "bg-sunken text-fg-3"
  }`}
  >
  {item.badge}
  </span>
  )}

  {selected && !item.badge && (
  <ChevronRight size={14} className={`shrink-0 ${group.hue.accent}`} />
  )}
  </>
  )}
  </button>
  </li>
  );
  })}
  </ul>
  </div>
  ))}
  </div>
  </nav>

 {user && (
 <div className="flex shrink-0 items-center gap-3 border-t border-line p-3">
 <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-[11px] font-bold uppercase text-brand-fg">
 {(user.name || user.email ||"?").slice(0, 1)}
 </span>
 {!collapsed && (
 <div className="min-w-0 flex-1">
 <p className="truncate text-xs font-semibold text-fg">
  {user.name ||t("shell.userFallback")}
 </p>
 <p className="truncate text-[10px] capitalize text-fg-3">
 {user.role} {user.ministry ? `· ${user.ministry}` :""}
 {user.project_id ? `· ${user.project_id}` :""}
 {language ? ` · ${languageLabel(language)}` :""}
 </p>
 </div>
 )}
 <button
 onClick={onLogout}
  title={t("common.signOut")}
  aria-label={t("common.signOut")}
 className="rounded-lg p-2 text-fg-3 transition hover:bg-risk-critical-subtle hover:text-risk-critical"
 >
 <LogOut size={15} />
 </button>
 </div>
 )}
 </div>
 </aside>
 );
}
