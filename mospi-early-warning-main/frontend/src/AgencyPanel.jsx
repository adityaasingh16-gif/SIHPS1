import { useEffect, useState } from"react";
import {
 Activity,
 AlertTriangle,
 Building2,
 CheckCircle2,
 FileUp,
 Flag,
 RefreshCw,
 Send,
} from"lucide-react";
import { useAuth } from"./AuthContext";
import { fetchAgencyDashboard, submitMilestone } from"./api";

export default function AgencyPanel() {
 const { token } = useAuth();
 const [dash, setDash] = useState(null);
 const [loading, setLoading] = useState(true);
 const [notice, setNotice] = useState(null);
 const [loadError, setLoadError] = useState("");

 const load = async () => {
 setLoading(true);
 try {
 setDash(await fetchAgencyDashboard(token));
 setLoadError("");
 } catch (e) {
 console.warn("Agency dashboard failed:", e);
 setLoadError(e.message || "Could not load your agency dashboard.");
 } finally {
 setLoading(false);
 }
 };

 useEffect(() => {
 load();
 }, [token]);

 const flash = (msg, tone ="ok") => {
 setNotice({ msg, tone });
 setTimeout(() => setNotice(null), 5000);
 };

 const handleSubmit = async (payload) => {
 try {
 await submitMilestone(token, payload);
 flash("Milestone submitted for ministry approval.");
 await load();
 return true;
 } catch (e) {
 flash(`Submit failed: ${e.message ||"unknown error"}`,"err");
 return false;
 }
 };

 if (loading && !dash) {
 return <div className="py-16 text-center text-sm text-fg-4">Loading agency dashboard…</div>;
 }
 if (!dash) {
 return (
 <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-risk-critical-border bg-risk-critical-subtle p-6 text-sm text-risk-critical" role="alert">
 <span>Could not load your agency dashboard: {loadError || "Check that your account has the agency role and a project scope."}</span>
 <button type="button" onClick={load} disabled={loading} className="rounded-lg border border-risk-critical-border px-3 py-1.5 font-semibold disabled:opacity-50">{loading ?"Retrying…" :"Retry"}</button>
 </div>
 );
 }

 const detail = dash.project_detail || {};
 const tracked = dash.milestones || [];

 return (
 <div className="space-y-6">
 <div className="flex flex-wrap items-center gap-3">
 <span className="inline-flex items-center gap-2 rounded-xl border border-brand-border bg-brand-subtle px-3 py-1.5 text-sm font-semibold text-brand-hover">
 <Building2 className="h-4 w-4" /> {dash.project_id}
 </span>
 <span className="rounded-xl border border-line bg-raised px-3 py-1.5 text-xs text-fg-3">
 {detail.sector} · {detail.ministry}
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

 {notice && (
 <div
 className={`rounded-xl border px-4 py-3 text-sm ${
 notice.tone ==="err"
 ?"border-risk-critical-border bg-risk-critical-subtle text-risk-critical"
 :"border-risk-low-border bg-risk-low-subtle text-risk-low"
 }`}
 >
 {notice.msg}
 </div>
 )}

 {/* Milestone submission form */}
 <Section title="Submit milestone update">
 <MilestoneForm onSubmit={handleSubmit} />
 </Section>

 {/* KPIs */}
 <div className="grid gap-4 sm:grid-cols-4">
 <Kpi icon={<Activity className="h-5 w-5" />} label="Physical progress" value={`${detail.physical_progress_pct ??"—"}%`} />
 <Kpi icon={<Flag className="h-5 w-5" />} label="Risk tier" value={detail.risk_tier ??"—"} tone="text-risk-high" />
 <Kpi icon={<AlertTriangle className="h-5 w-5" />} label="Delays flagged" value={tracked.filter((m) => m.flagged_delay).length} tone="text-risk-medium" />
 <Kpi icon={<CheckCircle2 className="h-5 w-5" />} label="Approved" value={tracked.filter((m) => m.status ==="approved").length} tone="text-risk-low" />
 </div>

 {/* Submission history */}
 <Section title="Submission & approval history">
 {tracked.length === 0 && <p className="px-5 py-4 text-sm text-fg-4">No submissions yet.</p>}
 <div className="divide-y divide-line">
 {tracked.map((m) => (
 <div key={m.id} className="px-5 py-3.5">
 <div className="flex items-center justify-between gap-2">
 <p className="text-sm font-semibold text-fg">{m.title}</p>
 <StatusBadge status={m.status} />
 </div>
 <p className="mt-1 text-xs text-fg-3">
 {m.description} · ₹{m.budget_spent_crore} Cr
 </p>
 <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-fg-4">
 <span>Submitted: {m.submitted_at}</span>
 {m.flagged_delay && <span className="font-semibold text-risk-high">⚠ {m.delay_note ||"delay flagged"}</span>}
 {m.decided_at && <span>Decision: {m.decided_at}</span>}
 {m.decision_note && <span>Note: {m.decision_note}</span>}
 </div>
 </div>
 ))}
 </div>
 </Section>

 {/* Uploads */}
 <Section title="Proof documents">
 <div className="flex flex-wrap gap-2 px-5 py-3">
 {(dash.uploads || []).map((d) => (
 <a
 key={d.id}
 href={`${import.meta.env.VITE_API_URL ||"/api"}${d.url.split("/public/docs").pop()}`.replace("/api/agency","/agency")}
 target="_blank"
 rel="noreferrer"
 className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-page px-3 py-1.5 text-xs font-medium text-fg-2 transition-colors hover:bg-sunken"
 >
 <FileUp className="h-3.5 w-3.5" /> {d.filename}
 </a>
 ))}
 {(dash.uploads || []).length === 0 && (
 <p className="text-sm text-fg-4">No documents uploaded.</p>
 )}
 </div>
 </Section>

 {/* Thread */}
 <Section title="Ministry ↔ Agency thread">
 <div className="space-y-2.5 px-5 py-4">
 {(dash.thread || []).map((n) => (
 <div
 key={n.id}
 className={`rounded-xl border px-3.5 py-2.5 text-sm ${
 n.sender_role ==="agency"
 ?"border-brand-border bg-brand-subtle text-brand-active"
 :"border-line bg-page text-fg-2"
 }`}
 >
 <div className="mb-1 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-fg-4">
 <span>{n.sender_role}</span>
 <span>{n.created_at}</span>
 </div>
 <p>{n.text}</p>
 </div>
 ))}
 {(dash.thread || []).length === 0 && (
 <p className="text-sm text-fg-4">No messages yet.</p>
 )}
 </div>
 </Section>
 </div>
 );
}

function Section({ title, children }) {
 return (
 <section className="rounded-2xl border border-line bg-raised">
 <header className="border-b border-line px-5 py-3">
 <h3 className="text-sm font-bold text-fg">{title}</h3>
 </header>
 {children}
 </section>
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

function StatusBadge({ status }) {
 const map = {
 approved:"bg-risk-low-subtle text-risk-low border-risk-low-border",
 rejected:"bg-risk-critical-subtle text-risk-critical border-risk-critical-border",
 pending:"bg-risk-medium-subtle text-risk-medium border-risk-medium-border",
 };
 return (
 <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize ${map[status] || map.pending}`}>
 {status}
 </span>
 );
}

function MilestoneForm({ onSubmit }) {
 const [title, setTitle] = useState("");
 const [description, setDescription] = useState("");
 const [spent, setSpent] = useState("");
 const [flag, setFlag] = useState(false);
 const [delayNote, setDelayNote] = useState("");
 const [submitting, setSubmitting] = useState(false);

 const submit = async (e) => {
 e.preventDefault();
 if (submitting || !title.trim() || spent ==="") return;
 setSubmitting(true);
 try {
 const saved = await onSubmit({
 title: title.trim(),
 description: description.trim() || title.trim(),
 budget_spent_crore: Number(spent),
 flagged_delay: flag,
 delay_note: flag ? delayNote.trim() : null,
 });
 if (!saved) return;
 setTitle(""); setDescription(""); setSpent(""); setFlag(false); setDelayNote("");
 } finally {
 setSubmitting(false);
 }
 };

 return (
 <form onSubmit={submit} className="grid gap-3 px-5 py-4 sm:grid-cols-2">
 <input
 value={title}
 onChange={(e) => setTitle(e.target.value)}
 placeholder="Milestone title (e.g. Package 3 — ROW acquired)"
 required
 className="rounded-xl border border-line bg-page px-3 py-2.5 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/40"
 />
 <input
 value={spent}
 onChange={(e) => setSpent(e.target.value)}
 placeholder="Budget spent (₹ Crore)"
 type="number"
 step="0.1"
 min="0"
 required
 className="rounded-xl border border-line bg-page px-3 py-2.5 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/40"
 />
 <textarea
 value={description}
 onChange={(e) => setDescription(e.target.value)}
 placeholder="Description of work done"
 rows={2}
 className="rounded-xl border border-line bg-page px-3 py-2.5 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/40 sm:col-span-2"
 />
 <label className="flex items-center gap-2 text-sm text-fg-2 sm:col-span-2">
 <input type="checkbox" checked={flag} onChange={(e) => setFlag(e.target.checked)} className="h-4 w-4 rounded accent-brand" />
 Flag anticipated delay
 </label>
 {flag && (
 <input
 value={delayNote}
 onChange={(e) => setDelayNote(e.target.value)}
 placeholder="Delay reason / expected impact"
 className="rounded-xl border border-line bg-page px-3 py-2.5 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/40 sm:col-span-2"
 />
 )}
 <button
 type="submit"
 disabled={submitting}
 className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-hover disabled:opacity-50 sm:col-span-2"
 >
 <Send className="h-4 w-4" /> {submitting ?"Submitting…" :"Submit for ministry approval"}
 </button>
 </form>
 );
}
