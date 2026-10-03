import { useEffect, useState, useCallback } from "react";
import { Brain, CheckCircle2, Lightbulb, RefreshCw, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { fetchProjectDetail, simulateProjectIntervention } from "../../api";
import { formatCr } from "../../lib/format";
import { riskColor } from "../../lib/risk";
import { riskBg } from "../../lib/risk";
import { getFeatureInfo } from "../../lib/featureLabels";
import { Metric } from "../../components/ui/Metric";
import { useT, useLocale } from "../../hooks/useT";
import { riskLabel } from "../../lib/risk";

export { ProjectModal };


function ProjectModal({ project, onClose, readOnly = false }) {
  const t = useT();
  const lang = useLocale();
  const [mlDetail, setMlDetail] = useState(null);

 // What-If Simulation State
 const [resolveLand, setResolveLand] = useState(false);
 const [resolveApproval, setResolveApproval] = useState(false);
 const [milestonesToClose, setMilestonesToClose] = useState(0);
 const [simResult, setSimResult] = useState(null);
 const [simulating, setSimulating] = useState(false);

 // Load live project ML detail (SHAP, suggested review, dependencies)
 useEffect(() => {
 let mounted = true;
 fetchProjectDetail(project.id).then((data) => {
 if (mounted && data) {
 setMlDetail(data);
 }
 });
 return () => {
 mounted = false;
 };
 }, [project.id]);

 // Execute What-If simulation with live ML inference
 const handleSimulate = useCallback(
 async (land, approval, milestones) => {
 setSimulating(true);
 try {
 const res = await simulateProjectIntervention(project.id, {
 resolve_land_issue: land,
 resolve_approval_bottleneck: approval,
 milestones_to_close: milestones,
 currentRisk: project.risk,
 });
 setSimResult(res);
 } catch (err) {
 console.error("Simulation failed:", err);
 } finally {
 setSimulating(false);
 }
 },
 [project.id, project.risk]
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

  const displayedRisk = simResult ? Math.round(simResult.simulated_risk_score) : project.risk;
  const riskDelta = simResult ? Math.round(simResult.delta) : 0;
  // The tier is derived from the score being displayed rather than read from
  // `project.status` / `simulated_risk_tier`, so the label can never disagree
  // with the number next to it.
  const displayedTier = riskLabel(displayedRisk, lang);
  const featureInfo = (item) => getFeatureInfo(item, lang);

 // Close on Escape
 useEffect(() => {
 const onKey = (e) => {
 if (e.key ==="Escape") onClose();
 };
 window.addEventListener("keydown", onKey);
 return () => window.removeEventListener("keydown", onKey);
 }, [onClose]);

 // Lock body scroll while modal is open
 useEffect(() => {
 const prev = document.body.style.overflow;
 document.body.style.overflow ="hidden";
 return () => {
 document.body.style.overflow = prev;
 };
 }, []);

 return (
 <div
  className="backdrop-enter fixed inset-0 z-50 flex items-end justify-center bg-scrim/60 backdrop-blur-sm sm:items-center sm:p-4"
 onClick={onClose}
 role="dialog"
 aria-modal="true"
 aria-label={project.name}
 >
 <div
 onClick={(e) => e.stopPropagation()}
 className="modal-enter flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-t-3xl bg-raised shadow-2xl sm:max-h-[90vh] sm:rounded-3xl"
 >
 <div className="flex items-start justify-between border-b border-line bg-raised p-5 md:p-6">
 <div className="min-w-0">
 <div className="flex flex-wrap items-center gap-2">
 <span className="rounded-full bg-brand-subtle px-2.5 py-0.5 text-[10px] font-bold text-brand-active uppercase tracking-widest">
 {project.id}
 </span>
 <span className="text-xs font-semibold text-fg-3">
 {project.sector}
 </span>
 </div>

 <h2 className="mt-2 max-w-3xl text-lg font-bold text-fg md:text-xl">
 {project.name}
 </h2>

  <p className="mt-1 text-xs text-fg-3">
  {t("modal.implementingAgency", { agency: project.organization })}
  </p>
  </div>

  <button
  onClick={onClose}
  autoFocus
  aria-label={t("modal.close")}
  className="pressable shrink-0 rounded-xl p-2 text-fg-3 transition hover:bg-sunken"
  >
  <X />
  </button>
  </div>

  <div className="min-h-0 space-y-6 overflow-y-auto p-5 md:p-6">
  {/* Top KPI row */}
  <div className="grid gap-4 md:grid-cols-4">
  <div className={`rounded-2xl border p-5 ${riskBg(displayedRisk)}`}>
  <p className="text-xs font-semibold" title={t("modal.combinedRiskTooltip")}>{t("modal.combinedRiskTier")}</p>
  <div className="flex items-baseline gap-2">
  <p className={`mt-2 text-4xl font-black ${riskColor(displayedRisk)}`}>
  {displayedRisk}
  </p>
  {simResult && (
  <span
  className={`text-xs font-bold ${
  riskDelta <= 0 ?"text-risk-low" :"text-risk-critical"
  }`}
  >
  ({riskDelta > 0 ?"+" :""}
  ({t("modal.pts", { sign: riskDelta > 0 ? "+" : "", n: riskDelta })})
  </span>
  )}
  </div>
  <p className="mt-1 text-xs text-fg-3">{t("modal.tier", { tier: displayedTier })}</p>
  </div>

  <Metric
  label={t("modal.schedulePressure")}
  value={mlDetail?.schedule_pressure_score != null ? `${mlDetail.schedule_pressure_score}/100` : "—"}
  />

  <Metric
  label={t("modal.mlCostRisk")}
  value={mlDetail?.cost_overrun_probability != null ? `${(mlDetail.cost_overrun_probability * 100).toFixed(1)}%` : "—"}
  />

  <Metric
  label={t("projects.originalCost")}
  value={formatCr(project.originalCost)}
  />

  <Metric
  label={t("modal.latestRevisedCost")}
  value={formatCr(project.revisedCost)}
  />

  <Metric
  label={t("projects.physicalProgress")}
  value={`${mlDetail?.physical_progress_pct ?? project.progress}%`}
  />
  </div>

 {/* Explainability & Suggestions */}
 <div className="grid gap-6 lg:grid-cols-2">
 {/* TreeSHAP Feature Attributions */}
 <div className="rounded-2xl border border-line p-5">
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
  const info = featureInfo(driver);
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
 className="bar-enter h-full rounded-full bg-risk-critical"
 style={{ "--w": `${info.widthPct}%`, width: `${info.widthPct}%` }}
 />
 </div>
 </div>
 );
 })}
 {mlDetail.mitigating_factors &&
  mlDetail.mitigating_factors.map((mit, idx) => {
  const info = featureInfo(mit);
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
 className="bar-enter h-full rounded-full bg-risk-low"
 style={{ "--w": `${info.widthPct}%`, width: `${info.widthPct}%` }}
 />
 </div>
 </div>
 );
 })}
 </>
 ) : (
  project.factors.map(([factor, value]) => (
  <div key={factor}>
  <div className="mb-1 flex justify-between text-xs">
  <span>{featureInfo({ name: factor }).label}</span>
  <span className="font-bold">{value}%</span>
  </div>
 <div className="h-2 rounded-full bg-sunken">
 <div
 className="h-full rounded-full bg-brand"
 style={{ width: `${value * 2}%` }}
 />
 </div>
 </div>
 ))
 )}
 </div>
 </div>

 {/* Suggested Interventions / Decision Memo */}
 <div className="rounded-2xl border border-line p-5">
 <div className="flex items-center gap-2">
 <Lightbulb size={18} className="text-risk-medium" />
  <h3 className="font-bold text-fg">{t("modal.decisionTitle")}</h3>
  </div>

  {mlDetail?.suggested_review ? (
  <div className="mt-4 rounded-xl bg-risk-medium-subtle/80 p-4 border border-risk-medium-border/60">
  <p className="text-xs font-bold uppercase tracking-wider text-risk-medium">
  {t("modal.reviewMemo")}
  </p>
 <p className="mt-2 text-xs leading-relaxed text-fg font-medium whitespace-pre-line">
 {mlDetail.suggested_review}
 </p>
 </div>
 ) : null}

 <div className="mt-4 space-y-2.5">
 {project.recommendations.map((rec) => (
 <div
 key={rec}
 className="flex gap-2.5 rounded-xl bg-page p-3 text-xs text-fg-2"
 >
 <CheckCircle2 size={15} className="shrink-0 text-brand mt-0.5" />
 <span>{rec}</span>
 </div>
 ))}
 </div>

 {mlDetail?.remarks_text && (
 <div className="mt-4 rounded-xl bg-page p-3 text-xs text-fg-2">
  <p className="font-semibold text-fg-2">{t("modal.latestRemarks")}</p>
 <p className="mt-1 italic">{mlDetail.remarks_text}</p>
 </div>
 )}
 </div>
 </div>

  {/* Interactive ML What-If Simulator. Hidden entirely in the public
      read-only build rather than disabled, so there is no control to click. */}
  {!readOnly && (
  <div className="rounded-3xl bg-inverse p-6 text-fg-inverse shadow-xl">
  <div className="flex items-center justify-between">
  <div className="flex items-center gap-2">
  <SlidersHorizontal size={18} className="text-brand-subtle-fg" />
   <h3 className="font-bold text-fg-inverse">{t("modal.simulatorTitle")}</h3>

   </div>
   {simulating && (
   <div className="flex items-center gap-2 text-xs text-brand-subtle-fg">
   <RefreshCw size={13} className="animate-spin" />
   {t("modal.rerunning")}
   </div>
   )}
   </div>

   <p className="mt-2 text-xs text-fg-inverse/70">{t("modal.simulatorSub")}</p>

 <div className="mt-5 grid gap-4 md:grid-cols-3">
 {/* Toggle 1: Land Clearance */}
 <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-fg-inverse/10 bg-fg-inverse/5 p-4 transition hover:bg-fg-inverse/10">
 <input
 type="checkbox"
 checked={resolveLand}
 onChange={onToggleLand}
 className="mt-0.5 h-4 w-4 rounded accent-brand"
 />
 <div>
   <span className="text-xs font-bold text-fg-inverse">{t("modal.resolveLand")}</span>
   <p className="mt-1 text-[11px] leading-relaxed text-fg-inverse/70">
   {t("modal.resolveLandSub")}
   </p>
 </div>
 </label>

 {/* Toggle 2: Statutory Clearances */}
 <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-fg-inverse/10 bg-fg-inverse/5 p-4 transition hover:bg-fg-inverse/10">
 <input
 type="checkbox"
 checked={resolveApproval}
 onChange={onToggleApproval}
 className="mt-0.5 h-4 w-4 rounded accent-brand"
 />
 <div>
   <span className="text-xs font-bold text-fg-inverse">{t("modal.expediteApprovals")}</span>
   <p className="mt-1 text-[11px] leading-relaxed text-fg-inverse/70">
   {t("modal.expediteApprovalsSub")}
   </p>
 </div>
 </label>

 {/* Slider 3: Milestone Acceleration */}
 <div className="rounded-2xl border border-fg-inverse/10 bg-fg-inverse/5 p-4">
 <div className="flex items-center justify-between text-xs">
   <span className="font-bold text-fg-inverse">{t("modal.accelerateMilestones")}</span>
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
   <p className="mt-1 text-[10px] text-fg-inverse/70">{t("modal.milestonesSub")}</p>
 </div>
 </div>

 {/* Simulation KPI Display */}
 <div className="mt-5 grid gap-3 md:grid-cols-4">
 <div className="rounded-xl bg-fg-inverse/5 p-3.5">
   <p className="text-[11px] text-fg-inverse/70">{t("modal.currentScore")}</p>
 <p className="mt-1 text-2xl font-bold">{project.risk}</p>
 </div>

 <div className="rounded-xl bg-fg-inverse/5 p-3.5">
   <p className="text-[11px] text-fg-inverse/70">{t("modal.simulatedScore")}</p>
 <p className="mt-1 text-2xl font-bold text-brand-subtle-fg">
 {displayedRisk}
 </p>
 </div>

 <div className="rounded-xl bg-fg-inverse/5 p-3.5">
   <p className="text-[11px] text-fg-inverse/70">{t("modal.riskDelta")}</p>
   <p
   className={`mt-1 text-2xl font-bold ${
   riskDelta <= 0 ?"text-risk-low" :"text-risk-critical"
   }`}
   >
    {t("modal.pts", { sign: riskDelta > 0 ? "+" : "", n: riskDelta })}
  </p>
   </div>

   <div className="rounded-xl bg-fg-inverse/5 p-3.5">
   <p className="text-[11px] text-fg-inverse/70">{t("modal.simulatedTier")}</p>
   <p className="mt-1 text-lg font-bold text-risk-medium">{displayedTier}</p>
   </div>
 </div>

  {simResult?.simulation_notes && (
  <p className="mt-4 rounded-xl bg-fg-inverse/5 p-3 text-xs leading-relaxed text-fg-inverse/80">
   💡 <span className="font-semibold">{t("modal.modelInsight")}</span>{""}
   {simResult.simulation_notes}
  </p>
  )}
  </div>
  )}

  {/* Model Lineage Banner */}
 <div className="rounded-2xl border border-brand-border bg-brand-subtle p-4">
 <div className="flex gap-3">
 <Sparkles className="shrink-0 text-brand mt-0.5" size={18} />
 <div>
   <h4 className="text-xs font-bold text-brand-active">{t("modal.lineageTitle")}</h4>
   <p className="mt-1 text-xs leading-relaxed text-brand-active">
   {t("modal.lineageBody", { time: project.timeRisk, cost: project.costRisk })}
   </p>
 </div>
 </div>
 </div>
 </div>
 </div>
 </div>
 );
}
