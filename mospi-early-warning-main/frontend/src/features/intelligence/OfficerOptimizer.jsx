import { useEffect, useState, useCallback } from "react";
import { Clock3, Cpu, Play, RefreshCw } from "lucide-react";
import { optimizeOfficerQueue } from "../../api";
import { useT } from "../../hooks/useT";

export { OfficerOptimizerWidget };

function OfficerOptimizerWidget() {
  const t = useT();
  const [availableHours, setAvailableHours] = useState(120);
 const [loading, setLoading] = useState(false);
 const [result, setResult] = useState(null);

 const handleSolve = useCallback(async (hours) => {
 const safeHours = typeof hours ==="number" && !isNaN(hours) ? hours : availableHours;
 setLoading(true);
 try {
 const data = await optimizeOfficerQueue(safeHours);
 setResult(data);
 } catch (e) {
 console.error(e);
 } finally {
 setLoading(false);
 }
 }, [availableHours]);

 useEffect(() => {
 let mounted = true;
 optimizeOfficerQueue(120).then((data) => {
 if (mounted && data) setResult(data);
 });
 return () => {
 mounted = false;
 };
 }, []);

 return (
 <div className="rounded-3xl border border-brand/20 bg-gradient-to-br from-fg via-brand-active to-fg p-6 text-white shadow-xl">
 <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
 <div>
 <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-brand/20 px-3 py-1 text-xs font-semibold text-brand-subtle-fg">
  <Cpu size={14} />
  {t("opt.badge")}
  </div>
  <h2 className="mt-2 text-xl font-bold tracking-tight">
  {t("opt.title")}
  </h2>
  <p className="mt-1 max-w-2xl text-xs leading-relaxed text-line-strong">
  {t("opt.subtitle")}
  </p>
 </div>

 <div className="flex flex-wrap items-center gap-3">
 <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-raised/5 px-4 py-2">
 <Clock3 size={16} className="text-brand-subtle-fg" />
  <span className="text-xs text-line-strong">{t("opt.reviewPool")}</span>
 <input
 type="number"
 min="20"
 max="500"
 step="10"
 value={availableHours}
 onChange={(e) => setAvailableHours(Math.max(10, Number(e.target.value)))}
 className="w-16 rounded-lg bg-raised/10 px-2 py-1 text-center text-sm font-bold text-white outline-none focus:ring-1 focus:ring-brand-subtle-fg"
 />
  <span className="text-xs text-fg-4">{t("opt.hrs")}</span>
 </div>

 <div className="flex gap-1.5">
 {[80, 120, 160].map((preset) => (
 <button
 key={preset}
 onClick={() => setAvailableHours(preset)}
 className={`rounded-xl px-2.5 py-1.5 text-xs font-semibold transition ${
 availableHours === preset
 ?"bg-brand text-white"
 :"bg-raised/10 text-line-strong hover:bg-raised/20"
 }`}
 >
  {t("opt.presetHours", { h: preset })}
  </button>
 ))}
 </div>

 <button
 onClick={() => handleSolve(availableHours)}
 disabled={loading}
 className="flex items-center gap-2 rounded-2xl bg-brand px-5 py-2.5 text-xs font-bold text-white shadow-lg transition hover:bg-brand-subtle-fg disabled:opacity-50"
 >
 {loading ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
  {t("opt.solve")}
  </button>
 </div>
 </div>

 {result && (
 <div className="mt-6 space-y-4">
 <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
 <div className="rounded-2xl border border-white/10 bg-raised/5 p-4">
  <p className="text-[11px] font-semibold uppercase text-fg-4">{t("opt.hoursAllocated")}</p>
  <p className="mt-1 text-2xl font-bold text-white">
  {result.total_hours_allocated}
  <span className="text-sm font-normal text-fg-4">
  {" "}
  {t("opt.ofAvailable", { total: result.available_hours })}
  </span>
  </p>
 </div>
 <div className="rounded-2xl border border-white/10 bg-raised/5 p-4">
  <p className="text-[11px] font-semibold uppercase text-fg-4">{t("opt.capacityUtilization")}</p>
 <p className="mt-1 text-2xl font-bold text-brand-subtle-fg">
 {result.capacity_utilization_pct}%
 </p>
 </div>
 <div className="rounded-2xl border border-white/10 bg-raised/5 p-4">
  <p className="text-[11px] font-semibold uppercase text-fg-4">{t("opt.totalRiskMitigated")}</p>
  <p className="mt-1 text-2xl font-bold text-risk-low">
  +{result.total_risk_mitigated} <span className="text-xs font-normal">{t("opt.pts")}</span>
  </p>
 </div>
 <div className="rounded-2xl border border-white/10 bg-raised/5 p-4">
  <p className="text-[11px] font-semibold uppercase text-fg-4">{t("opt.projectsSelected")}</p>
  <p className="mt-1 text-2xl font-bold text-risk-medium">
  {result.n_projects_selected}
  <span className="text-sm font-normal text-fg-4">
  {" "}
  {t("opt.ofQueue", { total: result.total_candidates })}
  </span>
  </p>
 </div>
 </div>

 <div className="overflow-hidden rounded-2xl border border-white/10 bg-raised/5">
 <div className="border-b border-white/10 px-4 py-3">
 <p className="text-xs font-semibold text-hover">
  {t("opt.queueTitle")}
  </p>
 </div>
 <div className="overflow-x-auto">
 <table className="w-full text-left text-xs text-line-strong">
 <thead className="border-b border-white/10 bg-raised/5 text-[11px] uppercase tracking-wider text-fg-4">
 <tr>
  <th className="px-4 py-2.5">{t("opt.col.rank")}</th>
  <th className="px-4 py-2.5">{t("opt.col.projectId")}</th>
  <th className="px-4 py-2.5">{t("opt.col.sector")}</th>
  <th className="px-4 py-2.5 text-center">{t("opt.col.compositeRisk")}</th>
  <th className="px-4 py-2.5 text-center">{t("opt.col.requiredHours")}</th>
  <th className="px-4 py-2.5 text-center">{t("opt.col.riskYield")}</th>
  <th className="px-4 py-2.5">{t("opt.col.bottleneck")}</th>
 </tr>
 </thead>
 <tbody className="divide-y divide-white/5">
 {result.selected_projects_queue &&
 result.selected_projects_queue.map((item, idx) => (
 <tr key={item.project_id} className="transition hover:bg-raised/5">
  <td className="px-4 py-3 font-bold text-brand-subtle-fg">{t("opt.rankValue", { n: idx + 1 })}</td>
 <td className="px-4 py-3 font-semibold text-white">{item.project_id}</td>
 <td className="px-4 py-3">{item.sector}</td>
 <td className="px-4 py-3 text-center">
 <span className="rounded-lg bg-risk-critical/20 px-2 py-0.5 font-bold text-risk-critical">
 {Math.round(item.composite_risk_score)}
 </span>
 </td>
  <td className="px-4 py-3 text-center font-medium">
  {t("opt.hoursValue", { h: item.required_review_hours })}
  </td>
  <td className="px-4 py-3 text-center font-bold text-risk-low">
  {t("opt.riskYieldValue", { n: Math.round(item.risk_reduction_impact) })}
  </td>
  <td className="max-w-xs truncate px-4 py-3 text-fg-4">
  {item.remarks_text || t("opt.fallbackRemarks")}
  </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>
 </div>
 </div>
 )}
 </div>
 );
}
