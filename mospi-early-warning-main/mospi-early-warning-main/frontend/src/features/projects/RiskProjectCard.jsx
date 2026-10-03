import { useState } from "react";
import { Brain, ChevronRight } from "lucide-react";
import { riskColor, riskLabel } from "../../lib/risk";
import { useLocale, useT } from "../../hooks/useT";

export { RiskProjectCard };


function RiskProjectCard({ project, onSelect }) {
  const t = useT();
  const lang = useLocale();
  const [showFactors, setShowFactors] = useState(false);

 return (
 <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm transition hover:shadow-md">
 <div className="flex items-start justify-between">
 <div>
 <span className="text-xs font-bold uppercase tracking-wider text-brand">
 {project.sector} • {project.id}
 </span>

 <h3 className="mt-2 font-bold text-fg">{project.name}</h3>
 <p className="text-xs text-fg-3">{project.organization}</p>
 </div>

 <div className="text-right">
  <p className="text-xs text-fg-4">{t("card.aiRisk")}</p>
  <p className={`text-3xl font-black ${riskColor(project.risk)}`}>
  {riskLabel(project.risk, lang)}
  </p>
 </div>
 </div>

 <div className="mt-5 grid grid-cols-2 gap-3">
 <div className="rounded-xl bg-risk-critical-subtle p-3">
  <p className="text-xs text-risk-critical">{t("card.costProb")}</p>
 <p className="mt-1 text-xl font-bold text-risk-critical">
 {project.costRisk}%
 </p>
 </div>

 <div className="rounded-xl bg-risk-high-subtle p-3">
  <p className="text-xs text-risk-high">{t("card.delayProb")}</p>
 <p className="mt-1 text-xl font-bold text-risk-high">
 {project.timeRisk}%
 </p>
 </div>
 </div>

 <div className="mt-4 flex gap-2">
 <button
 onClick={() => setShowFactors(!showFactors)}
 className="flex flex-1 items-center justify-between rounded-xl bg-page px-4 py-2.5 text-left text-xs font-semibold text-fg-2 hover:bg-sunken transition"
 >
 <span className="flex items-center gap-2">
  <Brain size={15} />
  {t("card.topDrivers")}
  </span>

 <ChevronRight
 size={15}
 className={showFactors ?"rotate-90 transition" :"transition"}
 />
 </button>

 {onSelect && (
 <button
 onClick={onSelect}
 className="flex items-center gap-1.5 rounded-xl bg-brand-subtle px-4 py-2.5 text-xs font-bold text-brand-hover transition hover:bg-brand-subtle"
 >
   {t("common.openProject")}
 </button>
 )}
 </div>

 {showFactors && (
 <div className="mt-3 space-y-3 rounded-xl border border-line p-4">
 {project.factors &&
 project.factors.map(([factor, value]) => (
 <div key={factor}>
 <div className="mb-1 flex justify-between text-xs">
 <span className="text-fg-2">{factor}</span>
 <span className="font-bold">{value}%</span>
 </div>

 <div className="h-1.5 rounded-full bg-sunken">
 <div
 className="h-full rounded-full bg-brand"
 style={{ width: `${Math.min(100, value * 1.5)}%` }}
 />
 </div>
 </div>
 ))}
 </div>
 )}
 </div>
 );
}
