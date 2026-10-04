import { useEffect, useState } from"react";
import {
 Activity,
 Building2,
 CheckCircle2,
 Clock3,
 RefreshCw,
 TrendingUp,
 XCircle,
} from"lucide-react";
import { useAuth } from"./AuthContext";
import { fetchMinistryDashboard, decideMilestone } from"./api";

export default function MinistryPanel() {
 const { token } = useAuth();
 const [dash, setDash] = useState(null);
 const [loading, setLoading] = useState(true);
 const [busyId, setBusyId] = useState(null);
 const [loadError, setLoadError] = useState("");
 const [actionError, setActionError] = useState("");

 const load = async () => {
 setLoading(true);
 try {
 setDash(await fetchMinistryDashboard(token));
 setLoadError("");
 } catch (e) {
 console.warn("Ministry dashboard failed:", e);
 setLoadError(e.message || "Could not load your ministry dashboard.");
 } finally {
 setLoading(false);
 }
 };

 useEffect(() => {
 load();
 }, [token]);

 const decide = async (id, approve) => {
 setBusyId(id);
 setActionError("");
 try {
 await decideMilestone(token, id, approve, approve ?"Approved by ministry" :"Rejected by ministry");
 await load();
 } catch (e) {
 setActionError(e.message || "The approval decision could not be saved.");
 } finally {
 setBusyId(null);
 }
 };

 if (loading && !dash) {
 return <div className="py-16 text-center text-sm text-fg-4">Loading ministry dashboard…</div>;
 }
 if (!dash) {
 return (
 <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-risk-critical-border bg-risk-critical-subtle p-6 text-sm text-risk-critical" role="alert">
 <span>Could not load your ministry dashboard: {loadError || "Check that your account has the ministry role and a ministry scope."}</span>
 <button type="button" onClick={load} disabled={loading} className="rounded-lg border border-risk-critical-border px-3 py-1.5 font-semibold disabled:opacity-50">{loading ?"Retrying…" :"Retry"}</button>
 </div>
 );
 }

 const pending = (dash.milestones || []).filter((m) => m.status ==="pending");

 return (
 <div className="space-y-6">
 <div className="flex flex-wrap items-center gap-3">
 <span className="inline-flex items-center gap-2 rounded-xl border border-brand-border bg-brand-subtle px-3 py-1.5 text-sm font-semibold text-brand-hover">
 <Building2 className="h-4 w-4" /> {dash.ministry}
 </span>
 <button
 type="button"
 onClick={load}
 disabled={loading}
 className="ml-auto inline-flex items-center gap-1.5 rounded-xl border border-line bg-raised px-3 py-1.5 text-xs font-semibold text-fg-2 transition-colors hover:bg-page disabled:opacity-50"
 >
 <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> {loading ?"Refreshing…" :"Refresh"}
 </button>
 </div>

 {loadError && (
 <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-risk-critical-border bg-risk-critical-subtle px-4 py-3 text-sm text-risk-critical" role="alert">
 <span>Dashboard refresh failed: {loadError}</span>
 <button type="button" onClick={load} disabled={loading} className="rounded-lg border border-risk-critical-border px-3 py-1 font-semibold disabled:opacity-50">Retry</button>
 </div>
 )}
 {actionError && <div className="rounded-xl border border-risk-critical-border bg-risk-critical-subtle px-4 py-3 text-sm text-risk-critical" role="alert">Decision failed: {actionError}</div>}

 {/* KPIs */}
 <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
 <Kpi icon={<Activity className="h-5 w-5" />} label="Projects" value={dash.total_projects} />
 <Kpi icon={<CheckCircle2 className="h-5 w-5" />} label="Ongoing" value={dash.active_projects} tone="text-risk-low" />
 <Kpi icon={<TrendingUp className="h-5 w-5" />} label="Delayed" value={dash.delayed_projects} tone="text-risk-high" />
 <Kpi icon={<Clock3 className="h-5 w-5" />} label="Pending Approvals" value={dash.pending_approvals} tone="text-risk-medium" />
 <Kpi icon={<TrendingUp className="h-5 w-5" />} label="Avg Risk" value={dash.avg_composite_risk} tone="text-brand" />
 </div>

 {/* Pending milestone approvals */}
 <section className="rounded-2xl border border-line bg-raised">
 <header className="border-b border-line px-5 py-3">
 <h3 className="text-sm font-bold text-fg">
 Approvals queue ·{dash.ministry}
 </h3>
 </header>
 <div className="divide-y divide-line">
 {pending.length === 0 && (
 <p className="px-5 py-6 text-center text-sm text-fg-4">No pending milestone submissions.</p>
 )}
 {pending.map((m) => (
 <div key={m.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
 <div>
 <p className="text-sm font-semibold text-fg">#{m.project_id} · {m.title}</p>
 <p className="mt-1 text-xs text-fg-3">{m.description}</p>
 <p className="mt-1.5 flex flex-wrap gap-3 text-[11px] text-fg-4">
 <span>Spend: ₹{m.budget_spent_crore} Cr</span>
 <span>Submitted: {m.submitted_at}</span>
 {m.flagged_delay && <span className="font-semibold text-risk-high">⚠ flagged delay</span>}
 </p>
 </div>
 <div className="flex shrink-0 gap-2">
 <button
 type="button"
 disabled={busyId === m.id}
 onClick={() => decide(m.id, true)}
 className="inline-flex items-center gap-1.5 rounded-xl bg-risk-low px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-risk-low disabled:opacity-50"
 >
 <CheckCircle2 className="h-4 w-4" /> Approve
 </button>
 <button
 type="button"
 disabled={busyId === m.id}
 onClick={() => decide(m.id, false)}
 className="inline-flex items-center gap-1.5 rounded-xl bg-risk-critical px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-risk-critical disabled:opacity-50"
 >
 <XCircle className="h-4 w-4" /> Reject
 </button>
 </div>
 </div>
 ))}
 </div>
 </section>

 {/* Budget chart (simple bars) */}
 <section className="rounded-2xl border border-line bg-raised p-5">
 <h3 className="text-sm font-bold text-fg">Budget vs Utilisation</h3>
 <div className="mt-4 space-y-3">
 {(dash.chart_budget || []).map((b) => (
 <div key={b.label}>
 <div className="mb-1 flex justify-between text-xs text-fg-3">
 <span>{b.label}</span>
 <span>₹{b.value} Cr</span>
 </div>
 <div className="h-3 overflow-hidden rounded-full bg-sunken">
 <div
 className="h-full rounded-full bg-brand"
 style={{ width: `${Math.min(100, (b.value / (dash.budget_total_crore || 1)) * 100)}%` }}
 />
 </div>
 </div>
 ))}
 <p className="pt-2 text-xs text-fg-3">
 Utilised {dash.budget_utilized_pct}% of ₹{dash.budget_total_crore} Cr sanctioned
 </p>
 </div>
 </section>

 {/* Risk distribution */}
 <section className="rounded-2xl border border-line bg-raised p-5">
 <h3 className="text-sm font-bold text-fg">Risk distribution</h3>
 <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
 {(dash.chart_risk || []).map((r) => (
 <div key={r.label} className="rounded-xl border border-line p-3 text-center">
 <p className="text-lg font-bold text-fg">{r.count}</p>
 <p className="text-[11px] font-medium uppercase tracking-wide text-fg-4">{r.label}</p>
 </div>
 ))}
 </div>
 </section>
 </div>
 );
}

function Kpi({ icon, label, value, tone ="text-brand" }) {
 return (
 <div className="rounded-2xl border border-line bg-raised p-4">
 <span className={tone}>{icon}</span>
 <p className="mt-2 text-xl font-bold text-fg">{value}</p>
 <p className="text-[11px] font-medium uppercase tracking-wide text-fg-4">{label}</p>
 </div>
 );
}
