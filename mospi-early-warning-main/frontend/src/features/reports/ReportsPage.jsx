import { useState } from "react";
import { Download, FileText } from "lucide-react";
import { API_BASE } from "../../api";

import { PageHeader } from "../../components/ui/PageHeader";
import { useT } from "../../hooks/useT";

export { ReportsPage };

function ReportsPage({ projectsList = [] }) {
  const t = useT();
  const [format, setFormat] = useState("html");
  const [limit, setLimit] = useState(200);
  const available = projectsList?.length ? projectsList : [];

  const reportsList = [
  {
  type:t("reports.executiveType"),
  title:t("reports.executiveTitle"),
  desc:t("reports.executiveDesc"),
  href: `${API_BASE}/reports/executive`,
  formats: ["html"],
  },
  {
  type:t("reports.registerType"),
  title:t("reports.registerTitle"),
  desc:t("reports.registerDesc"),
  href: `${API_BASE}/reports/projects?format=${format}&limit=${limit}`,
  formats: ["html","csv"],
  },
  {
  type:t("reports.alertsType"),
  title:t("reports.alertsTitle"),
  desc:t("reports.alertsDesc"),
  href: `${API_BASE}/reports/alerts?format=${format}`,
  formats: ["html","csv"],
  },
  {
  type:t("reports.ministryType"),
  title:t("reports.ministryTitle"),
  desc:t("reports.ministryDesc"),
  href: `${API_BASE}/reports/ministries`,
  formats: ["html"],
  },
  {
  type:t("reports.flashType"),
  title:t("reports.flashTitle"),
  desc:t("reports.flashDesc"),
  href: `${API_BASE}/reports/flash`,
  formats: ["pdf"],
  },
  ];

  const projectReports = available.slice(0, 8).map((p) => ({
  type:t("reports.diagnosticType"),
  title: t("reports.diagnosticTitle", { id: p.id }),
  desc: t("reports.diagnosticDesc", {
  sector: p.sector ||"—",
  risk: p.risk ?? "—",
  status: p.status ||"—",
  }),
  href: `${API_BASE}/reports/project/${encodeURIComponent(p.id)}`,
  formats: ["html"],
  }));

 const list = [...reportsList, ...projectReports];

 return (
 <div className="space-y-6">
  <PageHeader
  icon={FileText}
  title={t("reports.title")}
  subtitle={t("reports.subtitle")}
  />

  <div className="flex flex-wrap items-center justify-between gap-3">
  <div className="flex items-center gap-2">
  {available.length > 0 && (
  <select
  value={limit}
  onChange={(e) => setLimit(Number(e.target.value))}
  className="rounded-lg border border-line bg-raised px-3 py-2 text-sm text-fg-2 outline-none focus:border-brand"
  aria-label={t("reports.rowsPerReport")}
  >
  <option value={100}>{t("reports.rows100")}</option>
  <option value={200}>{t("reports.rows200")}</option>
  <option value={500}>{t("reports.rows500")}</option>
  </select>
  )}
  </div>
  <div className="flex items-center gap-2">
  <span className="text-xs font-medium text-fg-3">{t("reports.formatLabel")}</span>
  <div className="flex rounded-lg border border-line p-0.5">
  {[
  { id:"html", label:t("reports.formatHtml") },
  { id:"csv", label:t("reports.formatCsv") },
  ].map((f) => (
 <button
 key={f.id}
 type="button"
 onClick={() => setFormat(f.id)}
 className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
 format === f.id
 ?"bg-brand text-white"
 :"text-fg-3 hover:bg-sunken :bg-fg"
 }`}
 >
 {f.label}
 </button>
 ))}
 </div>
 </div>
 </div>

 <div className="space-y-3">
 {list.map((report, index) => (
 <div
 key={index}
 className="flex flex-col gap-4 rounded-2xl border border-line bg-raised p-5 shadow-sm md:flex-row md:items-center"
 >
 <div className="rounded-xl bg-brand-subtle p-3 text-brand-hover">
 <FileText size={20} />
 </div>

 <div className="flex-1">
 <p className="text-xs font-semibold uppercase tracking-wide text-brand">
 {report.type}
 </p>
 <h3 className="mt-1 font-bold text-fg">{report.title}</h3>
 <p className="mt-1 text-xs text-fg-3">{report.desc}</p>
  {report.formats.includes("csv") && format ==="csv" && (
  <p className="mt-1 text-[10px] text-fg-4">
  {t("reports.formatNote", { format: "CSV", n: limit })}
  </p>
  )}
 </div>

 <div className="flex shrink-0 items-center gap-2">
 <a
 href={report.href}
 download
 className="flex items-center gap-1.5 rounded-xl bg-brand px-4 py-2 text-xs font-semibold text-white hover:bg-brand-hover"
 >
  <Download size={14} /> {t("reports.download")}
  </a>
  <a
  href={report.href}
  target="_blank"
  rel="noreferrer"
  className="rounded-xl border border-line px-4 py-2 text-xs font-semibold text-fg-2 hover:bg-page :bg-fg"
  >
  {t("reports.view")}
  </a>
 </div>
 </div>
 ))}
 </div>
 </div>
 );
}
