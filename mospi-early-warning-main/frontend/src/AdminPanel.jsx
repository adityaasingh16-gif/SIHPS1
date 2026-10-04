import { useEffect, useState } from"react";
import {
  FileText,
  KeyRound,
  ShieldCheck,
  UserCheck,
  UserPlus,
  Users,
} from"lucide-react";
import { useAuth } from"./AuthContext";
import { AdminOperations } from"./features/admin/AdminOperations";
import { exportCSV } from"./lib/exportCsv";
import {
  fetchAdminUsers,
  fetchAdminAuditLogs,
  fetchAdminDashboard,
  assignUserRole,
  setUserAccess,
  createGovUser,
  resetUserPassword,
} from"./api";

const ROLE_COLORS = {
 admin:"bg-brand-subtle text-chart-3 border-brand-border",
 ministry:"bg-brand-subtle text-brand-hover border-brand-border",
 agency:"bg-brand-subtle text-brand-hover border-brand-border",
 viewer:"bg-risk-low-subtle text-risk-low border-risk-low-border",
 pending:"bg-risk-medium-subtle text-risk-medium border-risk-medium-border",
 revoked:"bg-risk-critical-subtle text-risk-critical border-risk-critical-border",
};

export default function AdminPanel() {
 const { token } = useAuth();
 const [users, setUsers] = useState([]);
 const [logs, setLogs] = useState([]);
 const [dash, setDash] = useState(null);
 const [notice, setNotice] = useState(null);
 const [coreLoading, setCoreLoading] = useState(true);
 const [coreError, setCoreError] = useState("");
 const [coreReload, setCoreReload] = useState(0);
 const [auditError, setAuditError] = useState("");
 const [auditReload, setAuditReload] = useState(0);

 const [showCreate, setShowCreate] = useState(false);
 const [form, setForm] = useState({
 email:"",
 name:"",
 role:"ministry",
 password:"",
 ministry:"",
 agency:"",
 project_id:"",
 });
 const [creating, setCreating] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [resetPw, setResetPw] = useState("");
  const [resetting, setResetting] = useState(false);

  // Audit trail filters. Empty strings are dropped by the API layer, so a
  // blank box means "no narrowing" rather than "match the empty string".
  const [auditAction, setAuditAction] = useState("");
  const [auditActor, setAuditActor] = useState("");
  const [auditSince, setAuditSince] = useState("");

  useEffect(() => {
  let cancelled = false;
  setCoreLoading(true);
  setCoreError("");
  Promise.allSettled([fetchAdminUsers(token), fetchAdminDashboard(token)])
  .then(([usersResult, dashboardResult]) => {
  if (cancelled) return;
  const errors = [];
  if (usersResult.status === "fulfilled") setUsers(usersResult.value);
  else errors.push(`Users: ${usersResult.reason?.message || "could not load"}`);
  if (dashboardResult.status === "fulfilled") setDash(dashboardResult.value);
  else errors.push(`Dashboard: ${dashboardResult.reason?.message || "could not load"}`);
  setCoreError(errors.join(" · "));
  })
  .finally(() => { if (!cancelled) setCoreLoading(false); });
  return () => { cancelled = true; };
  }, [token, coreReload]);

  // Refetched separately from the users/dashboard load so changing a filter
  // does not re-request the (much larger) user list.
  useEffect(() => {
  let cancelled = false;
  setAuditError("");
  fetchAdminAuditLogs(token, {
  action: auditAction || undefined,
  actor: auditActor || undefined,
  since: auditSince || undefined,
  })
  .then((data) => { if (!cancelled) setLogs(data); })
  .catch((err) => {
  if (cancelled) return;
  setLogs([]);
  setAuditError(err.message || "Could not load audit events.");
  });
  return () => { cancelled = true; };
  }, [token, auditAction, auditActor, auditSince, auditReload]);

 const flash = (msg) => {
 setNotice(msg);
 setTimeout(() => setNotice(null), 4000);
 };

 const handleAssign = async (u, role) => {
 try {
 await assignUserRole(token, u.id, role, null);
 flash(`${u.email} → ${role}`);
 setUsers(await fetchAdminUsers(token));
 } catch (e) {
 flash(`Error: ${e.message ||"assign failed"}`);
 }
 };

 const handleScope = async (u, scope) => {
 try {
 await assignUserRole(token, u.id, u.role, scope);
 flash(`${u.email} scoped to ${scope.ministry || scope.project_id || scope.agency ||"global"}`);
 setUsers(await fetchAdminUsers(token));
 } catch (e) {
 flash(`Error: ${e.message ||"scope failed"}`);
 }
 };

 const handleRevoke = async (u) => {
 const revoked = u.status !=="revoked";
 try {
 await setUserAccess(token, u.id, revoked,"Admin action");
 flash(`${u.email} ${revoked ?"revoked" :"reinstated"}`);
 setUsers(await fetchAdminUsers(token));
 } catch (e) {
 flash(`Error: ${e.message ||"update failed"}`);
 }
 };

 const handleCreate = async (e) => {
 e.preventDefault();
 setCreating(true);
 try {
 const payload = { ...form, email: form.email.trim(), name: form.name.trim() };
 if (payload.role !=="ministry") delete payload.ministry;
 if (payload.role !=="agency") {
 delete payload.agency;
 delete payload.project_id;
 }
 await createGovUser(token, payload);
 setShowCreate(false);
 setForm({ email:"", name:"", role:"ministry", password:"", ministry:"", agency:"", project_id:"" });
 flash(`Created ${payload.email} · initial password sent to them`);
 setUsers(await fetchAdminUsers(token));
 } catch (err) {
 flash(`Error: ${err.message ||"create failed"}`);
 } finally {
 setCreating(false);
 }
 };

 const handleResetPassword = async (e) => {
 e.preventDefault();
 setResetting(true);
 try {
 await resetUserPassword(token, resetTarget.id, resetPw);
 flash(`${resetTarget.email} → password reset (change forced on login)`);
 setResetTarget(null);
 setResetPw("");
 } catch (err) {
 flash(`Error: ${err.message ||"reset failed"}`);
 } finally {
 setResetting(false);
 }
 };

 const pendingUsers = users.filter((u) => u.status ==="pending");
 const activeUsers = users.filter((u) => u.status !=="revoked");
 const ministries = [...new Set(users.map((u) => u.ministry).filter(Boolean))];

 return (
 <div className="space-y-6">
 {notice && (
 <div className="rounded-xl border border-risk-low-border bg-risk-low-subtle px-4 py-3 text-sm text-risk-low">
 {notice}
 </div>
 )}
 {coreLoading && <p className="text-xs text-fg-4" role="status">Loading administration overview…</p>}
 {coreError && (
 <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-risk-critical-border bg-risk-critical-subtle px-4 py-3 text-sm text-risk-critical" role="alert">
 <span>Some administration data could not be loaded: {coreError}</span>
 <button type="button" onClick={() => setCoreReload((n) => n + 1)} className="rounded-lg border border-risk-critical-border px-3 py-1 font-semibold hover:bg-risk-critical/10">Retry</button>
 </div>
 )}

 {/* KPIs */}
 <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
 <Kpi icon={<Users className="h-5 w-5" />} label="Total Users" value={users.length} />
 <Kpi icon={<UserCheck className="h-5 w-5" />} label="Active" value={activeUsers.length} />
 <Kpi icon={<ShieldCheck className="h-5 w-5" />} label="Pending Appr." value={pendingUsers.length} tone="text-risk-medium" />
 <Kpi icon={<FileText className="h-5 w-5" />} label="Platform Projects" value={dash?.total_projects ??"—"} />
 </div>

 {/* Create account */}
 <section className="rounded-2xl border border-brand-border bg-raised">
 <header className="flex items-center justify-between border-b border-line px-5 py-3">
 <h3 className="flex items-center gap-2 text-sm font-bold text-fg">
 <UserPlus className="h-4 w-4 text-brand" /> Create government account
 </h3>
 <button
 type="button"
 onClick={() => setShowCreate((s) => !s)}
 className="rounded-lg border border-line px-3 py-1 text-xs font-semibold text-fg-2 transition-colors hover:border-brand hover:text-brand"
 >
 {showCreate ?"Hide" :"New user"}
 </button>
 </header>
 {showCreate && (
 <form onSubmit={handleCreate} className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-3">
 <Field label="Full name">
 <input
 required
 value={form.name}
 onChange={(e) => setForm({ ...form, name: e.target.value })}
 className={inputCls}
 placeholder="e.g. Ravi Kumar"
 />
 </Field>
 <Field label="Email">
 <input
 required
 type="email"
 value={form.email}
 onChange={(e) => setForm({ ...form, email: e.target.value })}
 className={inputCls}
 placeholder="user@gov.in"
 />
 </Field>
 <Field label="Role">
 <select
 value={form.role}
 onChange={(e) => setForm({ ...form, role: e.target.value })}
 className={inputCls}
 >
 <option value="ministry">Ministry</option>
 <option value="agency">Agency</option>
 <option value="viewer">Viewer (Public)</option>
 </select>
 </Field>
 {form.role ==="ministry" && (
 <Field label="Ministry">
 <input
 required
 value={form.ministry}
 onChange={(e) => setForm({ ...form, ministry: e.target.value })}
 className={inputCls}
 placeholder="e.g. Ministry of Petroleum & Natural Gas"
 />
 </Field>
 )}
 {form.role ==="agency" && (
 <>
 <Field label="Project ID">
 <input
 required
 value={form.project_id}
 onChange={(e) => setForm({ ...form, project_id: e.target.value })}
 className={inputCls}
 placeholder="e.g. PRJ_001"
 />
 </Field>
 <Field label="Agency">
 <input
 value={form.agency}
 onChange={(e) => setForm({ ...form, agency: e.target.value })}
 className={inputCls}
 placeholder="e.g. IOCL Project Cell"
 />
 </Field>
 </>
 )}
 <Field label="Initial password">
 <input
 required
 type="password"
 minLength={10}
 value={form.password}
 onChange={(e) => setForm({ ...form, password: e.target.value })}
 className={inputCls}
 placeholder="≥10 chars, upper+lower+digit+symbol"
 />
 </Field>
 <div className="sm:col-span-2 lg:col-span-3">
 <button
 type="submit"
 disabled={creating}
 className="flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand disabled:opacity-50"
 >
 <UserPlus className="h-4 w-4" />
 {creating ?"Creating…" :"Create account (sets initial password)"}
 </button>
 <p className="mt-2 text-[11px] text-fg-3">
 New government accounts must change their password on first login.
 </p>
 </div>
 </form>
 )}
 </section>

 {/* Pending approvals */}
 {pendingUsers.length > 0 && (
 <section className="rounded-2xl border border-risk-medium-border bg-raised">
 <header className="border-b border-line px-5 py-3">
 <h3 className="text-sm font-bold text-fg">
 Pending role assignment ({pendingUsers.length})
 </h3>
 </header>
 <div className="divide-y divide-line">
 {pendingUsers.map((u) => (
 <div key={u.id} className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
 <div>
 <p className="text-sm font-semibold text-fg">{u.name}</p>
 <p className="text-xs text-fg-3">{u.email}</p>
 </div>
 <div className="flex flex-wrap gap-1.5">
 {["admin","ministry","agency","viewer"].map((r) => (
 <button
 key={r}
 type="button"
 onClick={() => handleAssign(u, r)}
 className="rounded-lg border border-line px-2.5 py-1 text-xs font-semibold capitalize text-fg-2 transition-colors hover:border-brand hover:text-brand"
 >
 {r}
 </button>
 ))}
 </div>
 </div>
 ))}
 </div>
 </section>
 )}

 {/* User table (with scope management) */}
 <section className="overflow-hidden rounded-2xl border border-line bg-raised">
 <header className="border-b border-line px-5 py-3">
 <h3 className="text-sm font-bold text-fg">All users · role & scope</h3>
 </header>
 <div className="overflow-x-auto">
 <table className="w-full text-left text-sm">
 <thead className="border-b border-line text-xs uppercase tracking-wide text-fg-4">
 <tr>
 <th className="px-5 py-3 font-medium">User</th>
 <th className="px-5 py-3 font-medium">Role</th>
 <th className="px-5 py-3 font-medium">Scope</th>
 <th className="px-5 py-3 font-medium">Status</th>
 <th className="px-5 py-3 font-medium">Actions</th>
 </tr>
 </thead>
 <tbody className="divide-y divide-line">
 {users.map((u) => (
 <tr key={u.id} className="transition-colors hover:bg-page :bg-fg/50">
 <td className="px-5 py-3">
 <p className="font-semibold text-fg">{u.name}</p>
 <p className="text-xs text-fg-3">{u.email}</p>
 </td>
 <td className="px-5 py-3">
 <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize ${ROLE_COLORS[u.role] || ROLE_COLORS.pending}`}>
 {u.role}
 </span>
 </td>
 <td className="px-5 py-3">
 <div className="flex flex-wrap gap-1.5">
 {u.ministry && <ScopeChip label={u.ministry} />}
 {u.agency && <ScopeChip label={u.agency} tone="blue" />}
 {u.project_id && <ScopeChip label={u.project_id} tone="cyan" />}
 {!u.ministry && !u.agency && !u.project_id && <span className="text-xs text-fg-4">— global —</span>}
 </div>
 </td>
 <td className="px-5 py-3">
 <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize ${ROLE_COLORS[u.status] || ROLE_COLORS.pending}`}>
 {u.status}
 </span>
 </td>
 <td className="px-5 py-3">
 <div className="flex items-center gap-1.5">
 {u.status ==="pending" && (
 <>
 <button onClick={() => handleAssign(u,"ministry")} className="rounded-lg bg-brand px-2.5 py-1 text-xs font-semibold text-white hover:bg-brand-hover">+Ministry</button>
 <button onClick={() => handleAssign(u,"agency")} className="rounded-lg bg-brand px-2.5 py-1 text-xs font-semibold text-white hover:bg-brand-hover">+Agency</button>
 <button onClick={() => handleAssign(u,"viewer")} className="rounded-lg bg-risk-low px-2.5 py-1 text-xs font-semibold text-white hover:bg-risk-low">+Viewer</button>
 </>
 )}
 {u.status ==="active" && u.role ==="ministry" && (
 <select
 onChange={(e) => e.target.value && handleScope(u, { ministry: e.target.value })}
 className="rounded-lg border border-line bg-page px-2 py-1 text-xs"
 defaultValue=""
 >
 <option value="" disabled>Set ministry…</option>
 {ministries.map((m) => (
 <option key={m} value={m}>{m}</option>
 ))}
 </select>
 )}
 {u.status ==="active" && u.role ==="agency" && (
 <select
 onChange={(e) => e.target.value && handleScope(u, { project_id: e.target.value })}
 className="rounded-lg border border-line bg-page px-2 py-1 text-xs"
 defaultValue=""
 >
 <option value="" disabled>Set project…</option>
 {["PRJ_001","PRJ_002","PRJ_003","PRJ_004","PRJ_005","PRJ_006","PRJ_007"].map((p) => (
 <option key={p} value={p}>{p}</option>
 ))}
 </select>
 )}
 <button
 onClick={() => setResetTarget(u)}
 className="rounded-lg border border-line bg-page px-2.5 py-1 text-xs font-semibold text-fg-2 transition-colors hover:border-brand hover:text-brand"
 >
 <KeyRound className="mr-1 inline h-3 w-3" />Reset PW
 </button>
 <button
 onClick={() => handleRevoke(u)}
 disabled={u.role ==="admin" && u.id === u.id && u.status ==="active"}
 className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${
 u.status ==="revoked"
 ?"bg-risk-low text-white hover:bg-risk-low"
 :"bg-risk-critical text-white hover:bg-risk-critical"
 }`}
 >
 {u.status ==="revoked" ?"Reinstate" :"Revoke"}
 </button>
 </div>
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>
 </section>

  {/* Platform operations: public visibility, data ops, model health,
      milestone triage, document review, risk signals. */}
  <AdminOperations token={token} onNotice={flash} />

  {/* Audit log */}
  <section className="overflow-hidden rounded-2xl border border-line bg-raised">
  <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
  <h3 className="text-sm font-bold text-fg">Audit trail</h3>
  <div className="flex flex-wrap items-center gap-2">
  <input
  value={auditAction}
  onChange={(e) => setAuditAction(e.target.value)}
  placeholder="action contains…"
  className="w-40 rounded-lg border border-line bg-page px-2.5 py-1.5 text-xs outline-none focus:border-brand"
  />
  <input
  value={auditActor}
  onChange={(e) => setAuditActor(e.target.value)}
  placeholder="actor email…"
  className="w-44 rounded-lg border border-line bg-page px-2.5 py-1.5 text-xs outline-none focus:border-brand"
  />
  <input
  type="date"
  value={auditSince}
  onChange={(e) => setAuditSince(e.target.value)}
  title="Only events at or after this date"
  className="rounded-lg border border-line bg-page px-2.5 py-1.5 text-xs outline-none focus:border-brand"
  />
  {(auditAction || auditActor || auditSince) && (
  <button
  type="button"
  onClick={() => {
  setAuditAction("");
  setAuditActor("");
  setAuditSince("");
  }}
  className="rounded-lg border border-line bg-page px-2.5 py-1.5 text-xs font-semibold text-fg-2 transition-colors hover:border-brand hover:text-brand"
  >
  Clear
  </button>
  )}
  <button
  type="button"
  onClick={() =>
  exportCSV(
  "mospi-audit-trail.csv",
  logs.map((l) => ({
  id: l.id,
  at: l.created_at,
  action: l.action,
  actor: l.actor_email || "system",
  entity_type: l.entity_type || "",
  entity_ref: l.entity_ref || "",
  details: JSON.stringify(l.details || {}),
  })),
  )
  }
  disabled={logs.length === 0}
  className="rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-hover disabled:opacity-50"
  >
  Export CSV ({logs.length})
  </button>
  </div>
  </header>
  {auditError && (
  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-risk-critical-border bg-risk-critical-subtle px-5 py-2 text-xs text-risk-critical" role="alert">
  <span>Audit events failed to load: {auditError}</span>
  <button type="button" onClick={() => setAuditReload((n) => n + 1)} className="rounded-lg border border-risk-critical-border px-2.5 py-1 font-semibold hover:bg-risk-critical/10">Retry audit load</button>
  </div>
  )}
 <div className="overflow-x-auto">
 <table className="w-full text-left text-sm">
 <thead className="border-b border-line text-xs uppercase tracking-wide text-fg-4">
 <tr>
 <th className="px-5 py-3 font-medium">Action</th>
 <th className="px-5 py-3 font-medium">Entity</th>
 <th className="px-5 py-3 font-medium">Actor</th>
 <th className="px-5 py-3 font-medium">Ref</th>
 <th className="px-5 py-3 font-medium">At</th>
 </tr>
 </thead>
 <tbody className="divide-y divide-line">
 {logs.slice(0, 50).map((l) => (
 <tr key={l.id} className="transition-colors hover:bg-page :bg-fg/50">
 <td className="px-5 py-2.5 font-mono text-xs text-brand">{l.action}</td>
 <td className="px-5 py-2.5 text-xs text-fg-3">{l.entity_type}</td>
 <td className="px-5 py-2.5 text-xs text-fg-3">{l.actor_email ||"system"}</td>
 <td className="px-5 py-2.5 text-xs text-fg-4">{l.entity_ref}</td>
 <td className="px-5 py-2.5 text-xs text-fg-4">{l.created_at}</td>
 </tr>
 ))}
 {logs.length === 0 && (
 <tr><td colSpan={5} className="px-5 py-8 text-center text-sm text-fg-4">No audit events yet.</td></tr>
 )}
 </tbody>
 </table>
 </div>
 </section>

 {/* Reset password modal */}
 {resetTarget && (
  <div className="fixed inset-0 z-40 flex items-center justify-center bg-scrim/70 px-4 backdrop-blur-sm">
  <form onSubmit={handleResetPassword} className="w-full max-w-sm rounded-2xl border border-line bg-raised p-6 shadow-pop">
  <h4 className="flex items-center gap-2 text-sm font-bold text-fg">
  <KeyRound className="h-4 w-4 text-brand" /> Reset password
  </h4>
  <p className="mt-1 text-xs text-fg-3">
  New password for <span className="font-semibold text-fg-2">{resetTarget.email}</span>.
  The user will be forced to change it on next login.
  </p>
  <input
  required
  type="text"
  minLength={10}
  value={resetPw}
  onChange={(e) => setResetPw(e.target.value)}
  placeholder="Temporary password (≥10 chars)"
  className={`${inputCls} mt-4`}
  />
  <div className="mt-4 flex justify-end gap-2">
  <button
  type="button"
  onClick={() => { setResetTarget(null); setResetPw(""); }}
  className="rounded-lg border border-line-strong px-3 py-1.5 text-xs font-semibold text-fg-2 hover:border-line-heavy hover:bg-hover"
  >
  Cancel
  </button>
  <button
  type="submit"
  disabled={resetting}
  className="rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-brand-fg hover:bg-brand-hover disabled:opacity-50"
  >

 {resetting ?"Saving…" :"Reset password"}
 </button>
 </div>
 </form>
 </div>
 )}
 </div>
 );
}

function Kpi({ icon, label, value, tone ="text-brand" }) {
 return (
 <div className="rounded-2xl border border-line bg-raised p-5">
 <span className={tone}>{icon}</span>
 <p className="mt-3 text-2xl font-bold text-fg">{value}</p>
 <p className="text-xs font-medium uppercase tracking-wide text-fg-4">{label}</p>
 </div>
 );
}

function ScopeChip({ label, tone ="indigo" }) {
 const map = {
 indigo:"border-brand-border bg-brand-subtle text-brand-hover",
 blue:"border-brand-border bg-brand-subtle text-brand-hover",
 cyan:"border-risk-low-border bg-risk-low-subtle text-chart-2",
 };
 return (
 <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${map[tone]}`}>{label}</span>
 );
}

const inputCls ="w-full rounded-lg border border-line bg-page px-3 py-2 text-sm outline-none transition-colors focus:border-brand";

function Field({ label, children }) {
 return (
 <label className="block">
 <span className="mb-1 block text-xs font-medium text-fg-3">{label}</span>
 {children}
 </label>
 );
}
