import { useEffect, useMemo, useState, useCallback } from "react";
import { Activity, Brain, ChevronRight, CircleDollarSign, Clock3, Cpu, Lightbulb, RefreshCw, Search, SlidersHorizontal, Sparkles, TrendingUp } from "lucide-react";
import { fetchProjectDetail, simulateProjectIntervention, fetchModelComparison } from "../../api";
import { projects } from "../../data";

import { formatCr } from "../../lib/format";
import { riskColor } from "../../lib/risk";
import { riskBg } from "../../lib/risk";
import { isRealComparison } from "../../lib/model";
import { getFeatureInfo } from "../../lib/featureLabels";
import { riskLabel } from "../../lib/risk";
import { StatCard } from "../../components/ui/StatCard";
import { RiskBadge } from "../../components/ui/RiskBadge";
import { MetricCell } from "../../components/ui/MetricCell";
import { PageHeader } from "../../components/ui/PageHeader";
import { OfficerOptimizerWidget } from "../intelligence/OfficerOptimizer";
import { useT, useLocale } from "../../hooks/useT";

export { MLStudioPage };

function MLStudioPage({
  selectedProject,
  setSelectedProject,
  projectsList = [],
  hasLiveData = false,
  setActive: _setActive,
  readOnly = false,
}) {
  const t = useT();
  const lang = useLocale();
  const sourceProjects = projectsList.length > 0 ? projectsList : projects;

 // Active Project (fallback to highest risk project if none selected)
 const currentProject = useMemo(() => {
 if (selectedProject) return selectedProject;
 const sorted = [...sourceProjects].sort((a, b) => (b.risk || 0) - (a.risk || 0));
 return sorted[0] || sourceProjects[0];
 }, [selectedProject, sourceProjects]);

 const currentProjectId = currentProject?.id;
 const currentProjectRisk = currentProject?.risk;

 const [mlDetail, setMlDetail] = useState(null);
 const [modelComparison, setModelComparison] = useState(null);
  const [activeTab, setActiveTab] = useState(readOnly ? "comparison" : "simulator");
  // The simulator tab is the intervention surface, so the public read-only
  // build does not render it. Resolving the visible tab through this alias
  // means a stale "simulator" selection can never leave the page blank.
  const activeVisibleTab =
    readOnly && activeTab === "simulator" ? "comparison" : activeTab;
 const [projectSearch, setProjectSearch] = useState("");
 const [showProjectPicker, setShowProjectPicker] = useState(false);

 // What-If policy intervention levers
 const [resolveLand, setResolveLand] = useState(false);
 const [resolveApproval, setResolveApproval] = useState(false);
 const [milestonesToClose, setMilestonesToClose] = useState(0);
 const [simResult, setSimResult] = useState(null);
 const [simulating, setSimulating] = useState(false);

 const handleSelectProject = (p) => {
 if (setSelectedProject) setSelectedProject(p);
 setResolveLand(false);
 setResolveApproval(false);
 setMilestonesToClose(0);
 setSimResult(null);
 setShowProjectPicker(false);
 };

  // Load project details.
  //
  // Gated on the live feed arriving. The project list is seeded with demo
  // rows so the screen paints instantly, and those rows carry ids like
  // PRJ_006 that the database has never heard of, so requesting detail for
  // one is a guaranteed 404 on every page load.
  useEffect(() => {
  if (!currentProjectId || !hasLiveData) return;
  let mounted = true;

  fetchProjectDetail(currentProjectId).then((data) => {
  if (mounted && data) {
  setMlDetail(data);
  }
  });

  return () => {
  mounted = false;
  };
  }, [currentProjectId, hasLiveData]);

 // Load Model comparison
 useEffect(() => {
 let mounted = true;
 fetchModelComparison().then((data) => {
 if (mounted && data) {
 setModelComparison(data);
 }
 });
 return () => {
 mounted = false;
 };
 }, []);

 // Run What-If simulation
 const handleSimulate = useCallback(
 async (land, approval, milestones) => {
 if (!currentProjectId) return;
 setSimulating(true);
 try {
 const res = await simulateProjectIntervention(currentProjectId, {
 resolve_land_issue: land,
 resolve_approval_bottleneck: approval,
 milestones_to_close: milestones,
 currentRisk: currentProjectRisk,
 });
 setSimResult(res);
 } catch (err) {
 console.error("Simulation error:", err);
 } finally {
 setSimulating(false);
 }
 },
 [currentProjectId, currentProjectRisk]
 );

 const onToggleLand = () => {
 const next = !resolveLand;
 setResolveLand(next);
 handleSimulate(next, resolveApproval, milestonesToClose);
 };

 const onToggleApproval = () => {
 const next = !resolveApproval;
 setResolveApproval(next);
 handleSimulate(resolveLand, next, milestonesToClose);
 };

 const onChangeMilestones = (val) => {
 const num = Number(val);
 setMilestonesToClose(num);
 handleSimulate(resolveLand, resolveApproval, num);
 };

 const onResetInterventions = () => {
 setResolveLand(false);
 setResolveApproval(false);
 setMilestonesToClose(0);
 setSimResult(null);
 };

  const displayedRisk = simResult ? Math.round(simResult.simulated_risk_score) : (currentProject?.risk ?? 50);
  const riskDelta = simResult ? Math.round(simResult.delta) : 0;
  // Derived from the score on screen so the tier can never disagree with it.
  const displayedTier = riskLabel(displayedRisk, lang);

 // Filtered projects for selector
 const selectorMatches = useMemo(() => {
 const q = projectSearch.toLowerCase().trim();
 if (!q) return sourceProjects.slice(0, 15);
 return sourceProjects
 .filter(
 (p) =>
 p.id?.toLowerCase().includes(q) ||
 p.name?.toLowerCase().includes(q) ||
 p.sector?.toLowerCase().includes(q)
 )
 .slice(0, 15);
 }, [projectSearch, sourceProjects]);

 const topPriorityList = useMemo(() => {
 return [...sourceProjects].sort((a, b) => (b.risk || 0) - (a.risk || 0)).slice(0, 6);
 }, [sourceProjects]);

 return (
 <div className="space-y-6">
  <PageHeader
  icon={Brain}
  title={t("ml.title")}
  subtitle={t("ml.subtitle")}
  />

  {/* Model Architecture & Lineage Header Banner */}
  <div className="rounded-3xl border border-brand/30 bg-gradient-to-br from-inverse via-brand-active to-fg p-6 text-white shadow-xl">
  <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
  <div>
  <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-brand/20 px-3 py-1 text-xs font-semibold text-brand-subtle-fg">
  <Sparkles size={14} />
  {t("ml.coreBadge")}
  </div>
  <h2 className="mt-2 text-xl font-bold tracking-tight">{t("ml.engineTitle")}</h2>
  <p className="mt-1 max-w-2xl text-xs leading-relaxed text-line-strong">
  {t("ml.engineBody")}
  </p>
  </div>

  <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
  <div className="rounded-2xl border border-white/10 bg-raised/5 px-3.5 py-2">
  <p className="text-[10px] uppercase text-fg-4">{t("ml.metaModel")}</p>
  <p className="text-xs font-bold text-white">XGBoost + LightGBM</p>
  </div>
  <div className="rounded-2xl border border-white/10 bg-raised/5 px-3.5 py-2">
  <p className="text-[10px] uppercase text-fg-4">{t("ml.metaExplainability")}</p>
  <p className="text-xs font-bold text-brand-subtle-fg">TreeSHAP Engine</p>
  </div>
  <div className="rounded-2xl border border-white/10 bg-raised/5 px-3.5 py-2">
  <p className="text-[10px] uppercase text-fg-4">{t("ml.metaCalibration")}</p>
  <p className="text-xs font-bold text-risk-low">Platt Sigmoid (0-100)</p>
  </div>
  <div className="rounded-2xl border border-white/10 bg-raised/5 px-3.5 py-2">
  <p className="text-[10px] uppercase text-fg-4">{t("ml.metaOptimization")}</p>
  <p className="text-xs font-bold text-risk-medium">Google OR-Tools MILP</p>
  </div>
  </div>
  </div>
  </div>

 {/* Project Switcher Bar */}
 <div className="rounded-2xl border border-line bg-raised p-4 shadow-sm">
 <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
 <div className="flex flex-col items-stretch gap-2 lg:flex-row lg:items-center lg:gap-3">
  <span className="text-xs font-bold uppercase tracking-wide text-fg-4">
  {t("ml.activeProject")}
  </span>
 <div className="relative min-w-0">
 <button
  onClick={() => setShowProjectPicker(!showProjectPicker)}
  className="flex w-full min-w-0 items-center gap-2 rounded-xl border border-line bg-page px-3.5 py-2 text-left text-xs font-bold text-fg transition hover:border-brand-border hover:bg-brand-subtle/50 lg:w-auto"
 >
 <span className="shrink-0 rounded bg-brand-subtle px-1.5 py-0.5 text-[10px] text-brand-hover">
 {currentProject.id}
 </span>
 <span className="min-w-0 max-w-[280px] truncate">{currentProject.name}</span>
 <span className="shrink-0"><RiskBadge risk={currentProject.risk} /></span>
 <ChevronRight size={14} className={`shrink-0 ${showProjectPicker ?"rotate-90 transition" :"transition"}`} />
 </button>

 {/* Project Picker Dropdown */}
 {showProjectPicker && (
 <>
 <div className="fixed inset-0 z-40" onClick={() => setShowProjectPicker(false)} />
 <div className="absolute left-0 top-12 z-50 w-96 rounded-2xl border border-line bg-raised p-3 shadow-2xl">
 <div className="flex items-center gap-2 rounded-xl border border-line bg-page px-3 py-1.5">
 <Search size={14} className="text-fg-4" />
 <input
 value={projectSearch}
 onChange={(e) => setProjectSearch(e.target.value)}
  placeholder={t("ml.searchPlaceholder")}
 className="w-full bg-transparent text-xs text-fg outline-none placeholder:text-fg-4"
 autoFocus
 />
 </div>

 <div className="mt-2 max-h-60 space-y-1 overflow-y-auto">
 {selectorMatches.map((p) => (
 <button
 key={p.id}
 onClick={() => handleSelectProject(p)}
 className={`w-full rounded-xl p-2 text-left text-xs transition ${
 p.id === currentProject.id
 ?"bg-brand-subtle font-bold text-brand-hover"
 :"text-fg hover:bg-page"
 }`}
 >
 <div className="flex items-center justify-between">
 <span className="font-semibold text-fg-3">{p.id} • {p.sector}</span>
  <span className={`font-bold ${riskColor(p.risk)}`}>{t("ml.riskValue", { n: p.risk })}</span>
 </div>
 <p className="mt-0.5 line-clamp-1 font-medium">{p.name}</p>
 </button>
 ))}
 </div>
 </div>
 </>
 )}
 </div>
 </div>

 {/* Quick Priority Project Chips */}
 <div className="flex flex-wrap items-center gap-1.5 text-xs">
  <span className="mr-1 font-medium text-fg-4">{t("ml.quickSelect")}</span>
 {topPriorityList.map((p) => (
 <button
 key={p.id}
 onClick={() => handleSelectProject(p)}
 className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition ${
 p.id === currentProject.id
 ?"bg-brand text-white"
 :"bg-sunken text-fg-2 hover:bg-hover"
 }`}
 >
 {p.id} ({p.risk})
 </button>
 ))}
 </div>
 </div>
 </div>

  {/* Navigation Tabs. The What-If simulator is an intervention tool, so it is
      omitted from the public build rather than shown disabled. */}
  <div className="flex gap-2 border-b border-line pb-1">
  {!readOnly && (
  <button
  onClick={() => setActiveTab("simulator")}
  className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition ${
  activeVisibleTab ==="simulator"
  ?"bg-brand text-white shadow-sm"
  :"text-fg-2 hover:bg-sunken"
  }`}
  >
  <Sparkles size={15} />
  {t("ml.tabSimulator")}
  </button>
  )}

  <button
  onClick={() => setActiveTab("comparison")}
  className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition ${
  activeVisibleTab ==="comparison"
  ?"bg-brand text-white shadow-sm"
  :"text-fg-2 hover:bg-sunken"
  }`}
  >
  <TrendingUp size={15} />
  {t("ml.tabComparison")}
  </button>

  <button
  onClick={() => setActiveTab("optimizer")}
  className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition ${
  activeVisibleTab ==="optimizer"
  ?"bg-brand text-white shadow-sm"
  :"text-fg-2 hover:bg-sunken"
  }`}
  >
  <Cpu size={15} />
  {t("ml.tabOptimizer")}
  </button>
  </div>

  {/* TAB 1: Simulator & TreeSHAP */}
  {activeVisibleTab ==="simulator" && (
 <div className="space-y-6">
 {/* Top 4 Project KPI Cards */}
 <div className="grid gap-4 md:grid-cols-4">
 <div className={`rounded-2xl border p-5 ${riskBg(displayedRisk)} shadow-sm`}>
  <p className="text-xs font-semibold uppercase text-fg-3">{t("modal.aiRiskScore")}</p>
 <div className="mt-2 flex items-baseline gap-2">
 <span className={`text-4xl font-black ${riskColor(displayedRisk)}`}>
 {displayedRisk}
 </span>
 {simResult && (
 <span
 className={`text-xs font-bold ${
 riskDelta <= 0 ?"text-risk-low" :"text-risk-critical"
 }`}
 >
    ({t("modal.pts", { sign: riskDelta > 0 ? "+" : "", n: riskDelta })})
  </span>
 )}
 </div>
  <p className="mt-1 text-xs text-fg-3">{t("modal.tier", { tier: displayedTier })}</p>
  </div>

  <StatCard
  icon={Clock3}
  title={t("ml.scheduleDelayRisk")}
  value={`${currentProject.timeRisk || 76}%`}
  subtitle={t("ml.plattProb")}
  hue="rose"
  />

  <StatCard
  icon={CircleDollarSign}
  title={t("ml.costOverrunRisk")}
  value={`${currentProject.costRisk || 42}%`}
  subtitle={t("ml.plattProb")}
  hue="amber"
  />

  <StatCard
  icon={Activity}
  title={t("projects.physicalProgress")}
  value={`${mlDetail?.physical_progress_pct ?? currentProject.progress}%`}
  subtitle={t("ml.revisedCost", { cost: formatCr(currentProject.revisedCost) })}
  hue="fuchsia"
  />
  </div>

 <div className="grid gap-6 lg:grid-cols-2">
 {/* TreeSHAP Local Attributions */}
 <div className="rounded-2xl border border-line bg-raised p-6 shadow-sm">
 <div className="flex items-center justify-between">
 <div className="flex items-center gap-2">
 <Brain size={18} className="text-brand" />
  <h3 className="font-bold text-fg">{t("modal.shapTitle")}</h3>
  </div>
  {!mlDetail && (
  <RefreshCw size={14} className="animate-spin text-brand" />
  )}
  </div>
  <p className="mt-1 text-xs text-fg-3">{t("modal.shapSub")}</p>

 <div className="mt-4 space-y-3">
 {mlDetail?.top_risk_drivers && mlDetail.top_risk_drivers.length > 0 ? (
 <>
  {mlDetail.top_risk_drivers.map((driver, idx) => {
  const info = getFeatureInfo(driver, lang);
 const key = driver.feature_name || driver.factor_name || idx;
 return (
 <div key={key} className="rounded-xl bg-risk-critical-subtle/60 p-3">
 <div className="flex items-center justify-between text-xs">
 <span className="font-semibold text-fg">{info.label}</span>
 <span className="font-bold text-risk-critical">
 {info.formatted}
 </span>
 </div>
 <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-risk-critical-subtle">
 <div
 className="h-full rounded-full bg-risk-critical transition-all duration-300"
 style={{ width: `${info.widthPct}%` }}
 />
 </div>
 </div>
 );
 })}

 {mlDetail.mitigating_factors &&
  mlDetail.mitigating_factors.map((mit, idx) => {
  const info = getFeatureInfo(mit, lang);
 const key = mit.feature_name || mit.factor_name || idx;
 return (
 <div key={key} className="rounded-xl bg-risk-low-subtle/60 p-3">
 <div className="flex items-center justify-between text-xs">
 <span className="font-semibold text-fg">{info.label}</span>
 <span className="font-bold text-risk-low">
 {info.formatted}
 </span>
 </div>
 <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-risk-low-subtle">
 <div
 className="h-full rounded-full bg-risk-low transition-all duration-300"
 style={{ width: `${info.widthPct}%` }}
 />
 </div>
 </div>
 );
 })}
 </>
 ) : (
 currentProject.factors ? (
  currentProject.factors.map(([name, val]) => (
  <div key={name} className="rounded-xl bg-page p-3">
  <div className="flex items-center justify-between text-xs">
  <span className="font-semibold text-fg-2">{getFeatureInfo({ name }, lang).label}</span>
  <span className="font-bold text-risk-high">+{val}%</span>
  </div>
  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-hover">
  <div className="h-full rounded-full bg-risk-high" style={{ width: `${val}%` }} />
  </div>
  </div>
   ))
   ) : (
   <div className="py-6 text-center text-xs text-fg-4">{t("ml.loadingShap")}</div>
   )
   )}
  </div>

 {/* AI Project Doctor Policy Memorandum */}
 <div className="mt-5 rounded-xl border border-brand-border bg-brand-subtle/70 p-4">
 <div className="flex items-center gap-2 text-brand-active">
 <Lightbulb size={16} />
  <h4 className="text-xs font-bold uppercase tracking-wide">{t("ml.doctorMemo")}</h4>
  </div>
  <p className="mt-2 text-xs leading-relaxed text-brand-subtle-fg">
  {mlDetail?.suggested_review || t("ml.doctorFallback")}
  </p>
  {mlDetail?.remarks && (
  <p className="mt-2 border-t border-brand-border/60 pt-2 text-[11px] text-brand-active">
  <span className="font-semibold">{t("ml.contractorRemarks")}</span> {mlDetail.remarks}
  </p>
  )}
 </div>
 </div>

 {/* Interactive Policy Simulation Lab */}
 <div className="rounded-2xl border border-fg bg-fg p-6 text-white shadow-xl">
 <div className="flex items-center justify-between border-b border-white/10 pb-3">
 <div className="flex items-center gap-2">
 <SlidersHorizontal size={18} className="text-brand-subtle-fg" />
 <div>
  <h3 className="font-bold text-white">{t("ml.labTitle")}</h3>
  <p className="text-[11px] text-fg-4">{t("ml.labSub")}</p>
 </div>
 </div>
 {simulating && <RefreshCw size={14} className="animate-spin text-brand-subtle-fg" />}
 </div>

 <div className="mt-5 space-y-4">
 {/* Lever 1 */}
 <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-white/10 bg-raised/5 p-4 transition hover:bg-raised/10">
 <input
 type="checkbox"
 checked={resolveLand}
 onChange={onToggleLand}
 className="mt-0.5 h-4 w-4 rounded accent-brand"
 />
 <div>
  <span className="text-xs font-bold text-white">{t("ml.landLever")}</span>
  <p className="mt-0.5 text-[11px] text-fg-4">{t("ml.landLeverSub")}</p>
 </div>
 </label>

 {/* Lever 2 */}
 <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-white/10 bg-raised/5 p-4 transition hover:bg-raised/10">
 <input
 type="checkbox"
 checked={resolveApproval}
 onChange={onToggleApproval}
 className="mt-0.5 h-4 w-4 rounded accent-brand"
 />
 <div>
  <span className="text-xs font-bold text-white">{t("ml.clearanceLever")}</span>
  <p className="mt-0.5 text-[11px] text-fg-4">{t("ml.clearanceLeverSub")}</p>
 </div>
 </label>

 {/* Lever 3 */}
 <div className="rounded-2xl border border-white/10 bg-raised/5 p-4">
 <div className="flex items-center justify-between text-xs">
   <span className="font-bold text-white">{t("ml.milestoneLever")}</span>
 <span className="rounded bg-brand/20 px-2 py-0.5 font-bold text-brand-subtle-fg">
 +{milestonesToClose}
 </span>
 </div>
 <input
 type="range"
 min={0}
 max={5}
 step={1}
 value={milestonesToClose}
 onChange={(e) => onChangeMilestones(e.target.value)}
 className="mt-3 w-full accent-brand"
 />
   <p className="mt-1 text-[10px] text-fg-4">{t("modal.milestonesSub")}</p>
 </div>
 </div>

 {/* Simulation KPI Display */}
 <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
 <div className="rounded-xl bg-raised/5 p-3">
  <p className="text-[11px] text-fg-4">{t("ml.originalScore")}</p>
 <p className="mt-1 text-2xl font-bold">{currentProject.risk}</p>
 </div>
 <div className="rounded-xl bg-raised/5 p-3">
  <p className="text-[11px] text-fg-4">{t("modal.simulatedScore")}</p>
 <p className="mt-1 text-2xl font-bold text-brand-subtle-fg">{displayedRisk}</p>
 </div>
 <div className="rounded-xl bg-raised/5 p-3">
  <p className="text-[11px] text-fg-4">{t("modal.riskDelta")}</p>
 <p className={`mt-1 text-2xl font-bold ${riskDelta <= 0 ?"text-risk-low" :"text-risk-critical"}`}>
    {t("modal.pts", { sign: riskDelta > 0 ? "+" : "", n: riskDelta })}
  </p>
 </div>
 <div className="rounded-xl bg-raised/5 p-3">
  <p className="text-[11px] text-fg-4">{t("modal.simulatedTier")}</p>
  <p className="mt-1 text-lg font-bold text-risk-medium">{displayedTier}</p>
  </div>
 </div>

 {simResult?.simulation_notes && (
 <p className="mt-4 rounded-xl bg-raised/5 p-3 text-xs leading-relaxed text-line-strong">
  💡 <span className="font-semibold">{t("modal.modelInsight")}</span> {simResult.simulation_notes}
 </p>
 )}

 <div className="mt-5 flex justify-end">
 <button
 onClick={onResetInterventions}
 className="rounded-xl border border-white/20 px-4 py-2 text-xs font-semibold text-line-strong transition hover:bg-raised/10"
 >
  {t("ml.resetInterventions")}
  </button>
 </div>
 </div>
 </div>
 </div>
 )}

 {/* TAB 2: CUF vs Enhanced Model Benchmark */}
  {activeVisibleTab ==="comparison" && (
 <div className="space-y-6">
 <div className="rounded-2xl border border-brand-border bg-brand-subtle/70 p-5">
  <h3 className="text-base font-bold text-brand-active">
  {isRealComparison(modelComparison) ? t("ml.benchmarkReal") : t("ml.benchmarkSynthetic")}
  </h3>
  <p className="mt-1 text-xs leading-relaxed text-brand-active">
  {modelComparison?.comparison_summary || t("ml.benchmarkSummary")}
  </p>
 </div>

 <div className="grid gap-6 lg:grid-cols-2">
 {/* CUF Only Table */}
 <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
 <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
 <div>
  <h4 className="font-bold text-fg">{t("ml.cufBaseline")}</h4>
  <p className="text-xs text-fg-3">{t("ml.cufBaselineSub")}</p>
  </div>
  <span className="rounded-lg bg-sunken px-2.5 py-1 text-xs font-semibold text-fg-2">
  {t("ml.baseline")}
  </span>
 </div>

 <div className="overflow-x-auto">
 <table className="w-full text-left text-xs text-fg-2">
 <thead className="border-b border-line bg-page text-[10px] uppercase text-fg-4">
  <tr>
  <th className="px-3 py-2.5">{t("ml.predictiveTask")}</th>
  <th className="px-3 py-2.5">{t("ml.algorithm")}</th>
  <th className="px-3 py-2.5 text-center">{t("ml.metrics")}</th>
  </tr>
  </thead>
  <tbody className="divide-y divide-line">
  {modelComparison?.cuf_only_metrics ? (
 modelComparison.cuf_only_metrics.map((item, idx) => (
 <tr key={idx} className="hover:bg-page">
 <td className="px-3 py-3 font-semibold text-fg">{item.task}</td>
 <td className="px-3 py-3">{item.model}</td>
 <MetricCell item={item} />
 </tr>
 ))
 ) : (
 <>
  <tr>
  <td className="px-3 py-3 font-semibold">{t("ml.taskCostOverrun")}</td>
  <td className="px-3 py-3">{t("ml.modelCufCost")}</td>
  <td className="px-3 py-3 text-center font-bold">{t("ml.rocAuc", { v: "0.645" })}</td>
  </tr>
  <tr>
  <td className="px-3 py-3 font-semibold">{t("ml.taskMissedDeadline")}</td>
  <td className="px-3 py-3">{t("ml.modelCufDeadline")}</td>
  <td className="px-3 py-3 text-center font-bold">{t("ml.rocAuc", { v: "0.742" })}</td>
  </tr>
 </>
 )}
 </tbody>
 </table>
 </div>
 </div>

 {/* Enhanced Model Table */}
 <div className="rounded-2xl border border-risk-low-border bg-raised p-5 shadow-sm">
 <div className="mb-4 flex items-center justify-between border-b border-risk-low-border pb-3">
 <div>
  <h4 className="font-bold text-fg">{t("ml.enhancedModel")}</h4>
  <p className="text-xs text-fg-3">{t("ml.enhancedModelSub")}</p>
  </div>
  <span className="rounded-lg bg-risk-low-subtle px-2.5 py-1 text-xs font-semibold text-risk-low">
  {t("ml.lift")}
  </span>
 </div>

 <div className="overflow-x-auto">
 <table className="w-full text-left text-xs text-fg-2">
 <thead className="border-b border-line bg-risk-low-subtle/50 text-[10px] uppercase text-risk-low">
  <tr>
  <th className="px-3 py-2.5">{t("ml.predictiveTask")}</th>
  <th className="px-3 py-2.5">{t("ml.algorithm")}</th>
  <th className="px-3 py-2.5 text-center">{t("ml.metrics")}</th>
  </tr>
  </thead>
  <tbody className="divide-y divide-line">
  {modelComparison?.enhanced_data_metrics ? (
 modelComparison.enhanced_data_metrics.map((item, idx) => (
 <tr key={idx} className="hover:bg-risk-low-subtle/30">
 <td className="px-3 py-3 font-semibold text-fg">{item.task}</td>
 <td className="px-3 py-3">{item.model}</td>
 <MetricCell item={item} />
 </tr>
 ))
 ) : (
 <>
  <tr>
  <td className="px-3 py-3 font-semibold">{t("ml.taskCostOverrun")}</td>
  <td className="px-3 py-3">{t("ml.modelEnhCost")}</td>
  <td className="px-3 py-3 text-center font-bold text-risk-low">{t("ml.rocAuc", { v: "0.714" })}</td>
  </tr>
  <tr>
  <td className="px-3 py-3 font-semibold">{t("ml.taskMissedDeadline")}</td>
  <td className="px-3 py-3">{t("ml.modelEnhDeadline")}</td>
  <td className="px-3 py-3 text-center font-bold text-risk-low">{t("ml.rocAuc", { v: "0.788" })}</td>
  </tr>
 </>
 )}
 </tbody>
 </table>
 </div>
 </div>
 </div>
 </div>
 )}

 {/* TAB 3: Knapsack Optimizer */}
  {activeVisibleTab ==="optimizer" && (
 <div className="space-y-6">
 <OfficerOptimizerWidget />
 </div>
 )}
 </div>
 );
}
