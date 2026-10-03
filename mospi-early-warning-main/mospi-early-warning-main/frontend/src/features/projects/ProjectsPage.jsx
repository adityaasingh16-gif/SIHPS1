import { useMemo, useState } from "react";
import { ArrowUpRight, ChevronDown, Search, Target, X } from "lucide-react";
import { projects } from "../../data";
import { formatCr } from "../../lib/format";
import { riskTierKey, priorityScore } from "../../lib/risk";
import { useRiskLabel } from "../../hooks/useRiskLabel";
import { useT } from "../../hooks/useT";
import { RiskBadge } from "../../components/ui/RiskBadge";
import { ExportButton } from "../../components/ui/ExportButton";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState } from "../../components/ui/States";
import { Metric } from "../../components/ui/Metric";

export { ProjectsPage };

// Risk tiers as catalogue keys, not labels. The filter state holds the key, so
// it still matches after a language switch; only the rendered text changes.
const RISK_TIERS = [
  "common.critical",
  "common.high",
  "common.medium",
  "common.low",
];
const ALL = "all";


function ProjectsPage({ search ="", setSearch, setSelectedProject, projectsList = [] }) {
  const t = useT();
  const riskLabel = useRiskLabel();
  const [sector, setSector] = useState(ALL);
  const [risk, setRisk] = useState(ALL);

  const sourceProjects = projectsList.length > 0 ? projectsList : projects;
  const sectors = [ALL, ...new Set(sourceProjects.map((p) => p.sector).filter(Boolean))];

  const filtered = sourceProjects.filter((project) => {
  const q = search.toLowerCase().trim();
  const matchesSearch =
  !q ||
  (project.name && project.name.toLowerCase().includes(q)) ||
  (project.organization && project.organization.toLowerCase().includes(q)) ||
  (project.id && project.id.toLowerCase().includes(q)) ||
  (project.sector && project.sector.toLowerCase().includes(q)) ||
  (project.ministry && project.ministry.toLowerCase().includes(q)) ||
  (project.state && project.state.toLowerCase().includes(q));

  const matchesSector = sector === ALL || project.sector === sector;

  const matchesRisk = risk === ALL || riskTierKey(project.risk) === risk;

  return matchesSearch && matchesSector && matchesRisk;
  });

 // Deterministic ordering from original list
 const defaultOrder = useMemo(() => {
 const map = new Map();
 sourceProjects.forEach((p, i) => map.set(p.id, i));
 return map;
 }, [sourceProjects]);

 const [sortBy, setSortBy] = useState("priority");
 const [visibleCount, setVisibleCount] = useState(12);

 const sorted = useMemo(() => {
 const arr = [...filtered];
 switch (sortBy) {
 case"priority":
 return arr.sort(
 (a, b) =>
 priorityScore(b) - priorityScore(a) ||
 (b.risk || 0) - (a.risk || 0) ||
 (b.revisedCost || 0) - (a.revisedCost || 0),
 );
 case"risk":
 return arr.sort((a, b) => (b.risk || 0) - (a.risk || 0));
 case"cost":
 return arr.sort((a, b) => (b.revisedCost || 0) - (a.revisedCost || 0));
 case"progress":
 return arr.sort((a, b) => (b.progress || 0) - (a.progress || 0));
 case"name":
 return arr.sort((a, b) =>
 (a.name ||"").localeCompare(b.name ||""),
 );
 default:
 return arr.sort(
 (a, b) => (defaultOrder.get(a.id) ?? 0) - (defaultOrder.get(b.id) ?? 0),
 );
 }
 }, [filtered, sortBy, defaultOrder]);

 // Priority rank is computed over the filtered set, so it stays meaningful
 // while a sector or risk filter narrows the list.
 const priorityRank = useMemo(() => {
 const ranked = [...filtered].sort(
 (a, b) => priorityScore(b) - priorityScore(a),
 );
 return new Map(ranked.map((p, i) => [p.id, i + 1]));
 }, [filtered]);

  const visible = sorted.slice(0, visibleCount);

  // The empty state has to name which filters excluded the rows, otherwise
  // "no results" reads as "no data" and the user widens nothing.
  const emptyDescription = !search
    ? t("projects.noMatchNoSearch")
    : risk !== ALL && sector !== ALL
      ? t("projects.noMatchWithSectorRisk", {
          q: search,
          sector,
          risk: t(risk),
        })
      : sector !== ALL
        ? t("projects.noMatchWithSector", { q: search, sector })
        : risk !== ALL
          ? t("projects.noMatchWithRisk", { q: search, risk: t(risk) })
          : t("projects.noMatchWithSearch", { q: search });


  const exportRows = useMemo(
  () =>
  sorted.map((p) => ({
  ID: p.id,
  Name: p.name,
  Sector: p.sector,
  Organization: p.organization,
  "Original Cost (Cr)": p.originalCost,
  "Revised Cost (Cr)": p.revisedCost,
  "Progress %": p.progress,
  Completion: p.completionDate,
  "Risk Score": p.risk,
  "Risk Level": riskLabel(p.risk),
  "Cost Risk %": p.costRisk,
  "Time Risk %": p.timeRisk,
  Warnings: p.warnings ?? 0,
  })),
  [sorted, riskLabel],
  );

  return (
  <div className="space-y-6">
  <PageHeader
  icon={Target}
  title={t("shell.nav.highValue")}
  subtitle={t("projects.subtitle")}
  />

 <div className="grid gap-3 rounded-2xl border border-line bg-raised p-4 md:grid-cols-3">
 <div className="flex items-center gap-2 rounded-xl border border-line bg-page px-3 py-2 transition focus-within:border-brand focus-within:ring-2 focus-within:ring-brand-subtle">
 <Search size={16} className="shrink-0 text-fg-4" />
 <input
 value={search}
 onChange={(e) => setSearch && setSearch(e.target.value)}
 placeholder={t("projects.searchPlaceholder")}
 className="w-full bg-transparent text-sm text-fg outline-none placeholder:text-fg-4"
 />
 {search && (
 <button
 onClick={() => setSearch && setSearch("")}
 className="text-fg-4 hover:text-fg-2"
 title={t("shell.clearSearch")}
 >
 <X size={14} />
 </button>
 )}
 </div>

 <label className="relative">
 <span className="sr-only">{t("projects.filterBySector")}</span>
 <select
 value={sector}
 onChange={(e) => setSector(e.target.value)}
 className="w-full cursor-pointer appearance-none rounded-xl border border-line bg-page py-2 pl-3 pr-9 text-sm font-medium text-fg outline-none transition focus:border-brand focus:ring-2 focus:ring-brand-subtle"
 >
 {sectors.map((s) => (
 <option key={s} className="bg-raised text-fg">
 {s === ALL ? t("common.all") : s}
 </option>
 ))}
 </select>
 <ChevronDown
 size={16}
 className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-fg-4"
 />
 </label>

 <label className="relative">
 <span className="sr-only">{t("projects.filterByRisk")}</span>
 <select
 value={risk}
 onChange={(e) => setRisk(e.target.value)}
 className="w-full cursor-pointer appearance-none rounded-xl border border-line bg-page py-2 pl-3 pr-9 text-sm font-medium text-fg outline-none transition focus:border-brand focus:ring-2 focus:ring-brand-subtle"
 >
 <option className="bg-raised text-fg" value={ALL}>
 {t("common.all")}
 </option>
 {RISK_TIERS.map((key) => (
 <option key={key} className="bg-raised text-fg" value={key}>
 {t(key)}
 </option>
 ))}
 </select>
 <ChevronDown
 size={16}
 className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-fg-4"
 />
 </label>
 </div>

 <div className="flex flex-col gap-3 px-1 text-xs text-fg-3 md:flex-row md:items-center md:justify-between">
 <span>
 {t("projects.showing", { visible: visible.length, total: filtered.length })}
 {search && (
 <span>
 {t("projects.showingMatching", { q: search })}
 </span>
 )}
 </span>

 <div className="flex flex-wrap items-center gap-2">
 <select
 value={sortBy}
 onChange={(e) => setSortBy(e.target.value)}
 aria-label={t("projects.sortLabel")}
 className="rounded-xl border border-line bg-raised px-3 py-2 text-xs font-semibold text-fg-2 outline-none"
 >
 <option value="priority">{t("projects.sortPriority")}</option>
 <option value="risk">{t("projects.sortRisk")}</option>
 <option value="cost">{t("projects.sortCost")}</option>
 <option value="progress">{t("projects.sortProgress")}</option>
 <option value="name">{t("projects.sortName")}</option>
 <option value="original">{t("projects.sortDefault")}</option>
 </select>

 <ExportButton
 filename="mospi-high-value-projects.csv"
 rows={exportRows}
 />

 {(search || sector !== ALL || risk !== ALL) && (
 <button
 onClick={() => {
 if (setSearch) setSearch("");
 setSector(ALL);
 setRisk(ALL);
 }}
 className="font-semibold text-brand hover:underline"
 >
 {t("projects.resetFilters")}
 </button>
 )}
 </div>
 </div>

 {filtered.length > 0 ? (
 <div className="grid gap-4 xl:grid-cols-2">
 {visible.map((project) => (
 <button
 key={project.id}
 onClick={() => setSelectedProject(project)}
 className="group rounded-2xl border border-line bg-raised p-5 text-left shadow-sm transition hover:-translate-y-1 hover:border-brand-border hover:shadow-lg"
 >
 <div className="flex items-start justify-between gap-4">
 <div>
 <span className="text-xs font-bold uppercase tracking-wider text-brand">
 {project.sector} • {project.id}
 </span>

 <h3 className="mt-2 text-base font-bold text-fg">
 {project.name}
 </h3>

 <p className="mt-1 text-xs text-fg-3">
 {project.organization}
 </p>
 </div>

 <div className="flex shrink-0 flex-col items-end gap-2">
 {sortBy === "priority" && (
 <span
 title={t("projects.priorityTooltip", {
 score: Math.round(priorityScore(project)),
 })}
 className="rounded-full bg-brand-subtle px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-brand-subtle-fg"
 >
 {t("projects.priorityRank", { rank: priorityRank.get(project.id) })}
 </span>
 )}

 <RiskBadge risk={project.risk} />
 </div>
 </div>

 <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
 <Metric
 label={t("projects.originalCost")}
 value={formatCr(project.originalCost)}
 />
 <Metric
 label={t("projects.revisedCost")}
 value={formatCr(project.revisedCost)}
 />
 <Metric label={t("projects.progress")} value={`${project.progress}%`} />
 <Metric label={t("projects.completion")} value={project.completionDate} />
 </div>

 <div className="mt-5">
 <div className="mb-2 flex justify-between text-xs">
 <span className="text-fg-3">{t("projects.physicalProgress")}</span>
 <span className="font-semibold">{project.progress}%</span>
 </div>

 <div className="h-2 rounded-full bg-sunken">
 <div
 className="h-full rounded-full bg-brand transition-all"
 style={{ width: `${project.progress}%` }}
 />
 </div>
 </div>

 <div className="mt-4 flex items-center justify-between">
 <span className="text-xs font-medium text-fg-4">
 {t("projects.earlyWarningCount", { n: project.warnings })}
 </span>

 <span className="flex items-center gap-1 text-xs font-semibold text-brand opacity-0 transition group-hover:opacity-100">
 {t("projects.openIntelligence")} <ArrowUpRight size={14} />
 </span>
 </div>
 </button>
 ))}
 </div>
  ) : (
   <EmptyState
   icon={Target}
   tone="cyan"
   title={t("projects.noMatchTitle")}
   description={emptyDescription}
   actionLabel={t("projects.clearFilters")}
   onAction={() => {
   if (setSearch) setSearch("");
   setSector(ALL);
   setRisk(ALL);
   }}
   hint={
   sector !== ALL || risk !== ALL || search
   ? t("projects.filtersStillApplied")
   : undefined
   }
   />
   )}

 {filtered.length > visible.length && (
 <div className="pt-1 text-center">
 <button
 onClick={() => setVisibleCount((c) => c + 12)}
 className="rounded-xl border border-line bg-raised px-5 py-2.5 text-xs font-bold text-fg-2 shadow-sm transition hover:border-brand-border hover:text-brand-hover"
 >
 {t("projects.loadMore", {
 n: Math.min(12, filtered.length - visible.length),
 total: filtered.length,
 })}
 </button>
 </div>
 )}
 </div>
 );
}
