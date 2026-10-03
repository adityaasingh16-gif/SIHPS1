import { useEffect, useState } from "react";
import { Activity, AlertTriangle, ArrowUpRight, Bell, Brain, CalendarDays, CircleDollarSign, Clock3, ShieldAlert, Sparkles, TrendingUp } from "lucide-react";
import { fetchAlerts } from "../../api";
import { projects, alerts } from "../../data";
import { riskColor } from "../../lib/risk";
import { StatCard } from "../../components/ui/StatCard";
import { RiskBadge } from "../../components/ui/RiskBadge";
import { ExportButton } from "../../components/ui/ExportButton";
import { PageHeader } from "../../components/ui/PageHeader";
import { IntelligencePanel } from "../../components/ui/SectionPanel";
import { RiskProjectCard } from "../projects/RiskProjectCard";
import { OfficerOptimizerWidget } from "./OfficerOptimizer";
import { useT } from "../../hooks/useT";

export { IntelligencePage };


function IntelligencePage({ mode, setSelectedProject, projectsList = [], setActive }) {
  const t = useT();
  const sourceProjects = projectsList.length > 0 ? projectsList : projects;
 const criticalProjects = sourceProjects
 .filter((p) => p.risk >= 50)
 .sort((a, b) => b.risk - a.risk);

 const [liveAlerts, setLiveAlerts] = useState(alerts);
 const [severityFilter, setSeverityFilter] = useState("all");

 useEffect(() => {
 let mounted = true;
 fetchAlerts().then((data) => {
 if (mounted && data && data.length > 0) {
 setLiveAlerts(data);
 }
 });
 return () => {
 mounted = false;
 };
 }, []);

 if (mode ==="warnings") {
 const criticalCount = liveAlerts.filter((a) => a.severity ==="Critical").length;
 const highCount = liveAlerts.filter((a) => a.severity ==="High").length;
 const emergingCount = liveAlerts.length - criticalCount - highCount;

 const visibleAlerts =
 severityFilter ==="all"
 ? liveAlerts
 : liveAlerts.filter((a) => a.severity === severityFilter);

 return (
 <div className="space-y-6">
  <PageHeader
  icon={ShieldAlert}
  title={t("intel.warningsTitle")}
  subtitle={t("intel.warningsSubtitle")}
  />

  <div className="grid gap-4 md:grid-cols-3">
  <StatCard
  icon={AlertTriangle}
  title={t("common.critical")}
  value={criticalCount ||"8"}
  subtitle={t("intel.criticalSub")}
  accent="bg-risk-critical-subtle text-risk-critical"
  />

  <StatCard
  icon={Bell}
  title={t("common.high")}
  value={highCount ||"19"}
  subtitle={t("intel.highSub")}
  accent="bg-risk-high-subtle text-risk-high"
  />

  <StatCard
  icon={Activity}
  title={t("intel.emerging")}
  value={emergingCount > 0 ? emergingCount :"34"}
  subtitle={t("intel.emergingSub")}
  hue="fuchsia"
  />
  </div>

  <div className="flex flex-col gap-3 rounded-2xl border border-line bg-raised p-4 md:flex-row md:items-center md:justify-between">
  <div className="flex flex-wrap items-center gap-1.5">
  {[
  ["all", t("intel.filterAll", { n: liveAlerts.length })],
  ["Critical", t("intel.filterCritical", { n: criticalCount })],
  ["High", t("intel.filterHigh", { n: highCount })],
  ].map(([value, label]) => (
 <button
 key={value}
 onClick={() => setSeverityFilter(value)}
 className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
 severityFilter === value
 ? value ==="Critical"
 ?"bg-risk-critical text-white"
 : value ==="High"
 ?"bg-risk-high text-white"
 :"bg-fg text-white"
 :"bg-sunken text-fg-2 hover:bg-hover"
 }`}
 >
 {label}
 </button>
 ))}
 </div>

  <ExportButton
  label={t("common.exportCsv")}
  filename="mospi-early-warnings.csv"
  rows={visibleAlerts.map((a) => ({
  [t("intel.csvId")]: a.id,
  [t("intel.csvSeverity")]: a.severity,
  [t("intel.csvType")]: a.type || t("intel.predictiveSignal"),
  [t("intel.csvProject")]: a.project,
  [t("intel.csvMessage")]: a.message,
  [t("intel.csvScore")]: a.score ?? "",
  }))}
  />
 </div>

 <div className="space-y-3">
 {visibleAlerts.map((alert) => (
 <div
 key={alert.id}
 className="rounded-2xl border border-line bg-raised p-5 shadow-sm transition hover:shadow-md"
 >
 <div className="flex gap-4">
 <div
 className={`rounded-xl p-3 ${
 alert.severity ==="Critical"
 ?"bg-risk-critical-subtle text-risk-critical"
 :"bg-risk-high-subtle text-risk-high"
 }`}
 >
 <AlertTriangle size={20} />
 </div>

 <div className="flex-1">
 <div className="flex items-center justify-between">
 <div>
  <span className="text-xs font-semibold text-fg-4">
  {alert.type || t("intel.predictiveSignal")}
  </span>

 <h3 className="mt-1 font-bold text-fg">
 {alert.project}
 </h3>
 </div>

 <RiskBadge
 risk={
 alert.score ??
 (alert.severity ==="Critical"
 ? 90
 : alert.severity ==="High"
 ? 65
 : 40)
 }
 />
 </div>

 <p className="mt-2 text-sm text-fg-2">{alert.message}</p>

 <button
 onClick={() => {
 const matched = sourceProjects.find(
 (p) =>
 p.id === alert.project ||
 p.name?.includes(alert.project) ||
 alert.message?.includes(p.id)
 );
  if (matched && setSelectedProject) {
  setSelectedProject(matched);
  }
  }}
  className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-brand-hover hover:text-brand-active"
  >
   {t("common.openProject")} <ArrowUpRight size={14} />
  </button>
 </div>
 </div>
 </div>
 ))}
 </div>

 {visibleAlerts.length === 0 && (
 <div className="rounded-2xl border border-dashed border-line-strong bg-raised py-14 text-center">
 <ShieldAlert className="mx-auto text-fg-4" size={32} />
  <h3 className="mt-3 text-sm font-bold text-fg-2">
  {severityFilter !=="all"
  ? t("intel.noWarnings", { tier: t(`common.${severityFilter.toLowerCase()}`) })
  : t("intel.noWarningsAll")}
  </h3>
  <p className="mt-1 text-xs text-fg-3">{t("intel.noWarningsSub")}</p>
 </div>
 )}
 </div>
 );
 }

 if (mode ==="cost") {
 return (
  <IntelligencePanel
  title={t("intel.costTitle")}
  icon={CircleDollarSign}
  subtitle={t("intel.costSubtitle")}
  >
  <div className="grid gap-4 md:grid-cols-3">
  <StatCard
  icon={TrendingUp}
  title={t("intel.costRisk")}
  value="₹5.65L Cr"
  subtitle={t("intel.costRiskSub")}
  accent="bg-risk-high-subtle text-risk-high"
  />

  <StatCard
  icon={AlertTriangle}
  title={t("intel.highCostRisk")}
  value={criticalProjects.filter((p) => p.costRisk >= 50).length ||"127"}
  subtitle={t("intel.plattProbPct")}
  accent="bg-risk-critical-subtle text-risk-critical"
  />

  <StatCard
  icon={Brain}
  title={t("intel.model")}
  value={t("intel.ensemble")}
  subtitle={t("intel.ensembleSub")}
  hue="violet"
  />
  </div>

  <div className="mt-6 rounded-2xl bg-page p-5">
  <h3 className="font-bold">{t("intel.costDrivers")}</h3>

  <div className="mt-4 space-y-4">
  {[
  [t("intel.driverEscalation"), 82],
  [t("intel.driverBurn"), 68],
  [t("intel.driverDelay"), 54],
  [t("intel.driverMilestone"), 46],
  ].map(([name, value]) => (
 <div key={name}>
 <div className="mb-1 flex justify-between text-xs">
 <span>{name}</span>
 <span className="font-bold">{value}%</span>
 </div>

 <div className="h-2 rounded-full bg-raised">
 <div
 className="h-full rounded-full bg-risk-high"
 style={{ width: `${value}%` }}
 />
 </div>
 </div>
 ))}
 </div>
 </div>
 </IntelligencePanel>
 );
 }

 if (mode ==="time") {
 return (
  <IntelligencePanel
  title={t("intel.timeTitle")}
  icon={Clock3}
  subtitle={t("intel.timeSubtitle")}
  >
  <div className="grid gap-4 md:grid-cols-3">
  <StatCard
  icon={Clock3}
  title={t("intel.scheduleRisk")}
  value={criticalProjects.filter((p) => p.timeRisk >= 50).length ||"94"}
  subtitle={t("intel.scheduleRiskSub")}
  accent="bg-risk-high-subtle text-risk-high"
  />

  <StatCard
  icon={CalendarDays}
  title={t("intel.milestones")}
  value="286"
  subtitle={t("intel.milestonesSub")}
  hue="cyan"
  />

  <StatCard
  icon={TrendingUp}
  title={t("intel.leadTime")}
  value={t("intel.leadTimeValue")}
  subtitle={t("intel.leadTimeSub")}
  accent="bg-risk-low-subtle text-risk-low"
  />
  </div>

  <div className="mt-6 rounded-2xl border border-line p-5">
  <h3 className="font-bold">{t("intel.timeAnalysis")}</h3>

 <div className="mt-5 space-y-4">
 {criticalProjects.slice(0, 5).map((project) => (
 <div key={project.id}>
 <div className="flex items-center justify-between">
 <span className="text-sm font-semibold">{project.name}</span>

 <span className={riskColor(project.timeRisk)}>
 {project.timeRisk}%
 </span>
 </div>

 <div className="mt-2 h-2 rounded-full bg-sunken">
 <div
 className="h-full rounded-full bg-risk-high"
 style={{ width: `${project.timeRisk}%` }}
 />
 </div>
 </div>
 ))}
 </div>
 </div>
 </IntelligencePanel>
 );
 }

 return (
 <div className="space-y-6">
  <PageHeader
  icon={Brain}
  title={t("intel.analyticsTitle")}
  subtitle={t("intel.analyticsSubtitle")}
  />

 {/* Embedded OR-Tools MILP Knapsack Optimizer */}
 <OfficerOptimizerWidget />

  <div className="rounded-3xl bg-inverse p-7 text-fg-inverse shadow-xl">
 <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
 <div>
 <div className="flex items-center gap-2 text-brand-subtle-fg">
 <Sparkles size={18} />
  <span className="text-xs font-bold uppercase tracking-widest">
  {t("intel.doctorEyebrow")}
  </span>
  </div>

  <h2 className="mt-3 text-2xl font-bold">{t("intel.doctorHeadline")}</h2>

   <p className="mt-2 max-w-xl text-sm leading-6 text-fg-inverse/70">
   {t("intel.doctorBody")}
   </p>
   </div>

   <div className="rounded-2xl border border-fg-inverse/10 bg-fg-inverse/5 p-5 text-center">
   <p className="text-xs text-fg-inverse/70">{t("intel.portfolioAvg")}</p>
  <p className="mt-1 text-4xl font-bold text-risk-high">
  {Math.round(
  sourceProjects.reduce((acc, p) => acc + p.risk, 0) /
  (sourceProjects.length || 1)
  )}
  </p>
   <p className="mt-1 text-xs text-fg-inverse/70">{t("intel.calibratedIndex")}</p>

 </div>
 </div>
 </div>

 <div className="grid gap-4 lg:grid-cols-2">
 {criticalProjects.slice(0, 10).map((project) => (
 <RiskProjectCard
 key={project.id}
 project={project}
   onSelect={() => {
   if (setSelectedProject) setSelectedProject(project);
   }}
 />
 ))}
 </div>
 </div>
 );
}
