import { useMemo } from "react";
import { Activity, AlertTriangle, Building2, CircleDollarSign, Sparkles, TrendingUp } from "lucide-react";
import { getDataSource } from "../../api";
import { projects, alerts } from "../../data";
import { ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell } from "recharts";
import { formatLakhCrore } from "../../lib/format";
import { RISK_TIER_CHART_COLORS } from "../../lib/risk";
import { riskTrendOverall } from "../../lib/mockChartData";
import { progressData } from "../../lib/mockChartData";
import { riskDistribution } from "../../lib/mockChartData";
import { ChartTooltip } from "../../components/ui/ChartTooltip";
import { HeroKPI, CompactStat } from "../../components/ui/HeroKPI";
import { CostEscalationChart } from "../../components/ui/CostEscalationChart";
import { RiskBadge } from "../../components/ui/RiskBadge";
import { RiskFreshness } from "../../components/ui/RiskFreshness";
import { ConfusionMatrixCard } from "../../components/ui/ConfusionMatrix";
import { useT } from "../../hooks/useT";

export { DashboardHome };


function DashboardHome({ setSelectedProject, projectsList = [], setActive }) {
  const t = useT();
  const sourceProjects = projectsList.length > 0 ? projectsList : projects;
  // `projectsList` is pre-seeded with the bundled mock dataset, so a
  // non-empty list says nothing about provenance. Ask the API layer instead,
  // otherwise demo figures get captioned as live ML output.
  const hasLive = getDataSource() ==="live";

  // Count by the upstream English tier name, not by any rendered label:
  // `risk_tier`/`status` are data values used for equality checks, so they
  // must stay English even when the legend below is translated.
  const priorityData = useMemo(() => {
  const counts = { Low: 0, Medium: 0, High: 0, Critical: 0 };
  sourceProjects.forEach((p) => {
  const tier = p.risk_tier || p.status;
  if (counts[tier] !== undefined) counts[tier] += 1;
  });
  const total = counts.Low + counts.Medium + counts.High + counts.Critical;
  if (total === 0) return riskDistribution;
  return [
  { name:"Low", value: counts.Low },
  { name:"Medium", value: counts.Medium },
  { name:"High", value: counts.High },
  { name:"Critical", value: counts.Critical },
  ];
  }, [sourceProjects]);

  // Legend text is localised; the slice order must stay Low -> Critical to
  // line up with RISK_TIER_CHART_COLORS.
  const priorityLabels = {
  Low: t("common.low"),
  Medium: t("common.medium"),
  High: t("common.high"),
  Critical: t("common.critical"),
  };

  // `alerts` is bundled mock data, so `severity` is one of the four tier
  // names. Same English data value -> same translated label as the pie legend.
  const severityLabel = (name) => priorityLabels[name] || name;

 const totalOriginal = useMemo(
 () => sourceProjects.reduce((s, p) => s + (Number(p.originalCost) || 0), 0),
 [sourceProjects]
 );
 const totalRevised = useMemo(
 () => sourceProjects.reduce((s, p) => s + (Number(p.revisedCost) || 0), 0),
 [sourceProjects]
 );
 const totalExpenditure = useMemo(
 () => sourceProjects.reduce((s, p) => s + (Number(p.cumulativeExpenditure) || 0), 0),
 [sourceProjects]
 );

 const criticalCount = sourceProjects.filter((p) => p.risk >= 75).length;
 const highRiskCount = sourceProjects.filter((p) => p.risk >= 50 && p.risk < 75).length;
 const reviewCount = sourceProjects.filter((p) => p.risk >= 70).length;

 return (
 <div className="space-y-6">
 {/* The API layer silently swaps in a bundled sample dataset when the ML
 core is unreachable. Without this notice, sample figures are
 indistinguishable from live predictions. */}
 {!hasLive && (
 <div
 role="status"
 className="flex flex-wrap items-start gap-3 rounded-xl border border-risk-medium bg-risk-medium-subtle p-4 text-risk-medium"
 >
  <AlertTriangle size={18} className="mt-0.5 shrink-0 text-risk-medium" />
  <div className="min-w-0 flex-1">
  <p className="text-sm font-semibold">{t("dash.sampleTitle")}</p>
  <p className="mt-0.5 text-xs text-risk-medium">{t("dash.sampleBody")}</p>
  </div>
  </div>
  )}

  <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-inverse via-brand-active to-brand-active p-7 text-white shadow-card">
  <div className="relative max-w-3xl">
  <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-raised/10 px-3 py-1.5 text-xs font-medium text-brand-subtle">
  <Sparkles size={14} />
  {t("dash.eyebrow")}
  </div>

  <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
  {t("dash.heroLine1")}
  <span className="text-brand-subtle-fg">{t("dash.heroLine2")}</span>
  </h2>

  <p className="mt-4 max-w-2xl text-sm leading-6 text-line-strong">
  {t("dash.heroBody")}
  </p>
  </div>
   </section>

  {/* Hero + supporting tiles.
      Expenditure against revised cost is the figure people open this app for,
      so it gets the dominant panel; everything else steps down to a compact
      tile rather than competing in a row of identical cards. */}
  <div className="grid gap-4 lg:grid-cols-3">
  <div className="lg:col-span-2">
  <HeroKPI
  icon={Activity}
  label={t("dash.cumulativeExpenditure")}
  value={
  totalRevised > 0
  ? ((totalExpenditure / totalRevised) * 100).toFixed(1)
  : "0.0"
  }
  unit={t("dash.pctOfRevised")}
  caption={t("dash.spentAgainst", {
  spent: formatLakhCrore(totalExpenditure),
  revised: formatLakhCrore(totalRevised),
  })}
  progress={totalRevised > 0 ? (totalExpenditure / totalRevised) * 100 : 0}
  progressLabel={t("dash.progressLabel", {
  spent: formatLakhCrore(totalExpenditure),
  revised: formatLakhCrore(totalRevised),
  })}
  meta={[
  {
  label:t("common.projects"),
  value: sourceProjects.length.toLocaleString("en-IN"),
  },
  {
  label:t("dash.sanctioned"),
  value: formatLakhCrore(totalOriginal),
  },
  {
  label:t("dash.revised"),
  value: formatLakhCrore(totalRevised),
  },
  {
  label:t("dash.overrun"),
  value:
  totalOriginal > 0
  ? `+${(((totalRevised - totalOriginal) / totalOriginal) * 100).toFixed(1)}%`
  : "—",
  },
  {
  label:t("common.critical"),
  value: criticalCount.toLocaleString("en-IN"),
  },
  {
  label:t("common.high"),
  value: highRiskCount.toLocaleString("en-IN"),
  },
  ]}
  />
  </div>

  <div className="grid content-start gap-4 sm:grid-cols-2 lg:grid-cols-1">
  <CompactStat
  icon={Building2}
  label={t("dash.projectsMonitored")}
  value={sourceProjects.length.toLocaleString("en-IN")}
  subtitle={t("dash.acrossMinistries")}
  hue="cyan"
  />

  <CompactStat
  icon={CircleDollarSign}
  label={t("dash.sanctionedOutlay")}
  value={formatLakhCrore(totalOriginal)}
  subtitle={t("dash.originalApproved")}
  hue="violet"
  />

  <CompactStat
  icon={TrendingUp}
  label={t("dash.revisedCost")}
  value={formatLakhCrore(totalRevised)}
  subtitle={
  totalOriginal > 0
  ? t("dash.vsSanctioned", {
  pct: (((totalRevised - totalOriginal) / totalOriginal) * 100).toFixed(1),
  })
  : t("dash.sumLatest")
  }
  hue="amber"
  />
  </div>
  </div>

  {/* Sanctioned vs revised, per project: the escalation story had no visual
      at all before this - it existed only as two summed totals. */}
  <section className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
  <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
  <div>
  <h2 className="text-base font-bold tracking-tight text-fg">
  {t("dash.escalationTitle")}
  </h2>
  <p className="mt-1 text-xs text-fg-3">{t("dash.escalationSub")}</p>
  </div>
  <button
  type="button"
  onClick={() => setActive && setActive("projects")}
  className="rounded-lg border border-line px-3 py-1.5 text-xs font-semibold text-fg-2 transition hover:border-brand-border hover:bg-brand-subtle hover:text-brand-subtle-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
  >
  {t("dash.viewAllProjects")}
  </button>
  </div>

  <CostEscalationChart projects={sourceProjects} limit={12} />
  </section>

  {/* Risk posture — the decision-relevant numbers, lifted out of the
  previous hero banner so they are not duplicated above. */}
 <section className="card card-pad">
  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
  <div>
  <h3 className="card-title">{t("dash.riskPosture")}</h3>
  <p className="card-sub">{t("dash.riskPostureSub")}</p>
  </div>
  {hasLive && (
  <span className="badge bg-risk-low-subtle text-risk-low">
  {t("dash.liveBadge")}
  </span>
  )}
  </div>

  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
  {[
  { label:t("dash.criticalBand"), value: criticalCount, tone:"critical" },
  { label:t("dash.highBand"), value: highRiskCount, tone:"high" },
  { label:t("dash.reviewBand"), value: reviewCount, tone:"medium" },
  { label:t("dash.trackedProjects"), value: sourceProjects.length, tone:"low" },
  ].map((s) => (
 <div
 key={s.label}
 className="rounded-xl border border-line bg-sunken px-4 py-3"
 >
 <p
 className={`text-2xl font-bold tabular-nums text-risk-${s.tone}`}
 >
 {s.value.toLocaleString("en-IN")}
 </p>
 <p className="mt-0.5 text-xs text-fg-3">{s.label}</p>
 </div>
 ))}
 </div>
 </section>

 <div className="grid gap-6 xl:grid-cols-3">
 <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm xl:col-span-2">
  <div className="mb-5 flex items-center justify-between">
  <div>
  <h3 className="font-bold text-fg">{t("dash.riskTrend")}</h3>
  <p className="text-xs text-fg-3">{t("dash.riskTrendSub")}</p>
  </div>

  <div className="flex items-center gap-2">
  <RiskFreshness compact />
  <span className="rounded-lg bg-brand-subtle px-3 py-1.5 text-xs font-semibold text-brand-hover">
  {t("dash.aiAnalytics")}
  </span>
  </div>
  </div>

 <div className="h-[280px]">
 <ResponsiveContainer width="100%" height="100%">
 <AreaChart data={riskTrendOverall}>
 <defs>
  <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.3} />
  <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
  </linearGradient>
  </defs>

  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />

  <XAxis
    dataKey="month"
    fontSize={12}
    tick={{ fill: "var(--fg-muted)" }}
    axisLine={{ stroke: "var(--border-default)" }}
    tickLine={false}
  />

  <YAxis
    fontSize={12}
    domain={[40, 60]}
    tick={{ fill: "var(--fg-muted)" }}
    axisLine={false}
    tickLine={false}
  />

  <Tooltip content={<ChartTooltip />} />

  <Area
    type="monotone"
  dataKey="overall"
  name={t("dash.overallSeries")}
    stroke="var(--chart-1)"
    fill="url(#riskFill)"
    strokeWidth={2.5}
  />
 </AreaChart>
 </ResponsiveContainer>
 </div>
 </div>

 <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
  <div className="mb-4">
  <h3 className="font-bold text-fg">{t("dash.priorityDistribution")}</h3>
  <p className="text-xs text-fg-3">
  {hasLive ? t("dash.priorityLive") : t("dash.priorityDefault")}
  </p>
  </div>

 <div className="h-[220px]">
 <ResponsiveContainer width="100%" height="100%">
 <PieChart>
 <Pie
 data={priorityData}
 dataKey="value"
 innerRadius={62}
 outerRadius={88}
 paddingAngle={3}
 >
  {priorityData.map((_, index) => (
  <Cell
    key={index}
  fill={RISK_TIER_CHART_COLORS[index % RISK_TIER_CHART_COLORS.length]}
  />
  ))}
  </Pie>

  <Tooltip content={<ChartTooltip />} />
 </PieChart>
 </ResponsiveContainer>
 </div>

 <div className="grid grid-cols-2 gap-2">
 {priorityData.map((item, index) => {
 const total = priorityData.reduce((acc, it) => acc + it.value, 0);
 const pct = total > 0 ? Math.round((item.value / total) * 100) : 0;
 return (
 <div
 key={item.name}
 className="flex items-center justify-between rounded-lg bg-page px-3 py-2"
 >
 <div className="flex items-center gap-2 text-xs text-fg-2">
  <span
  className="h-2 w-2 rounded-full"
  style={{
  backgroundColor: RISK_TIER_CHART_COLORS[index % RISK_TIER_CHART_COLORS.length],
  }}
  />
  <span>{priorityLabels[item.name] || item.name}</span>
 </div>

 <span className="font-bold text-fg">{pct}%</span>
 </div>
 );
 })}
 </div>
 </div>
 </div>

 <div className="grid gap-6 xl:grid-cols-3">
 <div className="xl:col-span-3">
 <ConfusionMatrixCard />
 </div>
 </div>

 <div className="grid gap-6 lg:grid-cols-2">
 <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
 <div className="mb-5 flex items-center justify-between">
  <div>
  <h3 className="font-bold">{t("dash.sectorProgress")}</h3>
  <p className="text-xs text-fg-3">{t("dash.sectorProgressSub")}</p>
  </div>

  <span className="text-xs font-semibold text-brand-hover">{t("dash.live")}</span>
 </div>

 <div className="h-[260px]">
 <ResponsiveContainer width="100%" height="100%">
  <BarChart data={progressData}>
  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
  <XAxis
    dataKey="name"
    fontSize={11}
    tick={{ fill: "var(--fg-muted)" }}
    axisLine={{ stroke: "var(--border-default)" }}
    tickLine={false}
  />
  <YAxis
    fontSize={11}
    tick={{ fill: "var(--fg-muted)" }}
    axisLine={false}
    tickLine={false}
  />
  <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--surface-hover)" }} />
  <Bar dataKey="progress" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
  </BarChart>
 </ResponsiveContainer>
 </div>
 </div>

 <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
 <div className="mb-5 flex items-center justify-between">
  <div>
  <h3 className="font-bold">{t("dash.warningQueue")}</h3>
  <p className="text-xs text-fg-3">{t("dash.warningQueueSub")}</p>
  </div>

  <span className="rounded-full bg-risk-critical-subtle px-3 py-1 text-xs font-semibold text-risk-critical">
  {t("dash.activeCount", { n: alerts.length })}
  </span>
 </div>

 <div className="space-y-3">
 {alerts.map((alert) => (
 <div
 key={alert.id}
 className="flex items-start gap-3 rounded-xl border border-line bg-page p-3"
 >
 <div className="rounded-lg bg-risk-critical-subtle p-2 text-risk-critical">
 <AlertTriangle size={16} />
 </div>

 <div className="min-w-0">
 <p className="text-sm font-semibold text-fg">
 {alert.project}
 </p>

 <p className="mt-1 text-xs leading-5 text-fg-3">
 {alert.message}
 </p>
 </div>

  <span className="ml-auto text-[10px] font-bold uppercase text-risk-critical">
  {severityLabel(alert.severity)}
  </span>
 </div>
 ))}
 </div>
 </div>
 </div>

 <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
 <div className="mb-5 flex items-center justify-between">
  <div>
  <h3 className="font-bold">{t("dash.highPriority")}</h3>
  <p className="text-xs text-fg-3">{t("dash.highPrioritySub")}</p>
  </div>

  <button
  onClick={() => setActive && setActive("projects")}
  className="text-xs font-semibold text-brand-hover transition hover:text-brand-active"
  >
  {t("dash.viewAllArrow")}
  </button>
 </div>

 <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
 {sourceProjects
 .filter((p) => p.risk >= 50)
 .slice(0, 4)
 .map((project) => (
 <button
 key={project.id}
 onClick={() => setSelectedProject(project)}
 className="rounded-xl border border-line p-4 text-left transition hover:-translate-y-1 hover:border-brand-border hover:shadow-md"
 >
 <div className="flex items-center justify-between">
 <span className="text-[10px] font-bold uppercase text-fg-4">
 {project.sector}
 </span>

 <RiskBadge risk={project.risk} />
 </div>

 <p className="mt-3 line-clamp-2 text-sm font-semibold text-fg">
 {project.name}
 </p>

 <div className="mt-4">
  <div className="mb-1 flex justify-between text-[10px] text-fg-3">
  <span>{t("dash.physicalProgress")}</span>
  <span>{project.progress}%</span>
  </div>

 <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
 <div
 className="h-full rounded-full bg-brand"
 style={{ width: `${project.progress}%` }}
 />
 </div>
 </div>
 </button>
 ))}
 </div>
 </div>
 </div>
 );
}
