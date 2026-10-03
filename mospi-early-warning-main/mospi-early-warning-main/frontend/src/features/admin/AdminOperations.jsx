import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Database,
  FileWarning,
  Globe,
  HardDrive,
  MessageSquare,
  MessageSquareWarning,
  RefreshCw,
  Search,
  Tags,
  Trash2,
  Cpu,
  CheckCircle2,
  XCircle,
} from "lucide-react";

import {
  deleteAdminDocument,
  decideAdminSubmission,
  fetchAdminComplaints,
  fetchAdminDocuments,
  fetchAdminMessageNotes,
  fetchAdminModelHealth,
  fetchAdminPublicRowPage,
  fetchAdminRemarkSignals,
  fetchAdminSubmissions,
  fetchAdminSystemMeta,
  runAdminSeedDatabase,
  updateAdminComplaint,
  updateAdminPublicRow,
} from "../../api";

const PAGE_SIZE = 100;

const inputCls =
  "w-full rounded-lg border border-line bg-page px-3 py-2 text-sm outline-none transition-colors focus:border-brand";

const btnPrimary =
  "rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-hover disabled:opacity-50";
const btnGhost =
  "rounded-lg border border-line bg-page px-3 py-1.5 text-xs font-semibold text-fg-2 transition-colors hover:border-brand hover:text-brand disabled:opacity-50";

function Card({ icon, title, subtitle, children, actions }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-raised">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-bold text-fg">
            {icon}
            {title}
          </h3>
          {subtitle && <p className="mt-0.5 text-xs text-fg-3">{subtitle}</p>}
        </div>
        {actions}
      </header>
      {children}
    </section>
  );
}

function Empty({ children }) {
  return <p className="px-5 py-8 text-center text-sm text-fg-4">{children}</p>;
}

function kb(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function AdminOperations({ token, onNotice }) {
  const [publicRows, setPublicRows] = useState([]);
  const [rowTotal, setRowTotal] = useState(0);
  const [hiddenTotal, setHiddenTotal] = useState(0);
  const [rowSearch, setRowSearch] = useState("");
  const [rowFilter, setRowFilter] = useState("all");
  const [rowOffset, setRowOffset] = useState(0);
  const [savingRow, setSavingRow] = useState(null);

  const [ops, setOps] = useState(null);
  const [health, setHealth] = useState(null);
  const [seeding, setSeeding] = useState(false);

  const [subs, setSubs] = useState([]);
  const [subFilter, setSubFilter] = useState("pending");
  const [deciding, setDeciding] = useState(null);

  const [docs, setDocs] = useState([]);
  const [removingDoc, setRemovingDoc] = useState(null);

  const [signals, setSignals] = useState([]);
  const [notes, setNotes] = useState([]);

  const [complaints, setComplaints] = useState([]);
  const [complaintFilter, setComplaintFilter] = useState("");
  const [savingComplaint, setSavingComplaint] = useState(null);
  // Notes are typed per row and only sent on blur/change, so the list does not
  // re-render on every keystroke of an unrelated complaint's note.
  const [draftNotes, setDraftNotes] = useState({});

  // "all" is the absence of a server-side filter; the other two map onto the
  // endpoint's `visible` flag.
  const visibleParam = rowFilter === "all" ? undefined : rowFilter === "public" ? 1 : 0;

  const loadRows = useCallback(() => {
    const opts = { token, limit: PAGE_SIZE, offset: rowOffset, search: rowSearch || undefined, visible: visibleParam };
    return fetchAdminPublicRowPage(opts)
      .then(({ rows, total }) => {
        setPublicRows(rows);
        setRowTotal(total ?? rows.length);
      })
      .catch(() => {
        setPublicRows([]);
        setRowTotal(0);
      });
  }, [token, rowOffset, rowSearch, visibleParam]);

  /**
   * Every panel loads once on mount. A failure degrades that panel to its
   * empty state rather than blanking the page, so one broken endpoint cannot
   * hide the other five.
   */
  const loadAll = useCallback(() => {
    loadRows();
    // A second, page-size-1 call purely to label the "Hidden" filter: the
    // current page may not contain every hidden row.
    fetchAdminPublicRowPage({ token, limit: 1, visible: 0 })
      .then(({ total }) => setHiddenTotal(total ?? 0))
      .catch(() => setHiddenTotal(0));
    fetchAdminSystemMeta(token).then(setOps).catch(() => setOps(null));
    fetchAdminModelHealth(token).then(setHealth).catch(() => setHealth(null));
    fetchAdminSubmissions(token, { status: subFilter || undefined })
      .then((d) => setSubs(Array.isArray(d) ? d : []))
      .catch(() => setSubs([]));
    fetchAdminDocuments(token).then((d) => setDocs(Array.isArray(d) ? d : [])).catch(() => setDocs([]));
    fetchAdminRemarkSignals(token).then((d) => setSignals(Array.isArray(d) ? d : [])).catch(() => setSignals([]));
    fetchAdminMessageNotes(token).then((d) => setNotes(Array.isArray(d) ? d : [])).catch(() => setNotes([]));
    fetchAdminComplaints(token, { status: complaintFilter || undefined })
      .then((d) => setComplaints(Array.isArray(d) ? d : []))
      .catch(() => setComplaints([]));
  }, [token, subFilter, complaintFilter, loadRows]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const toggleVisibility = async (row) => {
    setSavingRow(row.project_id);
    try {
      await updateAdminPublicRow(token, row.project_id, {
        is_public_visible: !row.is_public_visible,
      });
      onNotice(
        `${row.project_id} ${row.is_public_visible ? "hidden from" : "published to"} the public portal`,
      );
      loadAll();
    } catch (e) {
      onNotice(`Error: ${e.message || "visibility update failed"}`);
    } finally {
      setSavingRow(null);
    }
  };

  const saveSummary = async (row) => {
    setSavingRow(row.project_id);
    try {
      // Only the summary key is sent, so visibility is left as-is.
      await updateAdminPublicRow(token, row.project_id, { public_summary: row.public_summary || "" });
      onNotice(`${row.project_id} summary updated`);
    } catch (e) {
      onNotice(`Error: ${e.message || "summary update failed"}`);
    } finally {
      setSavingRow(null);
    }
  };

  const runSeed = async () => {
    setSeeding(true);
    try {
      const res = await runAdminSeedDatabase(token);
      onNotice(
        `Seed complete — ${res.projects_seeded ?? "?"} projects, ` +
          `${res.snapshots_seeded ?? "?"} snapshots, ${res.predictions_seeded ?? "?"} predictions` +
          (res.models_saved_to ? ` · models → ${res.models_saved_to}` : ""),
      );
      loadAll();
    } catch (e) {
      onNotice(`Error: ${e.message || "seed failed"}`);
    } finally {
      setSeeding(false);
    }
  };

  const decide = async (submission, approve) => {
    setDeciding(submission.id);
    try {
      await decideAdminSubmission(token, submission.id, approve, "Admin escalation");
      onNotice(`${submission.project_id} · "${submission.title}" ${approve ? "approved" : "rejected"}`);
      setSubs(await fetchAdminSubmissions(token, { status: subFilter || undefined }));
    } catch (e) {
      onNotice(`Error: ${e.message || "decision failed"}`);
    } finally {
      setDeciding(null);
    }
  };

  /**
   * Moves a complaint through triage, optionally saving a note in the same
   * call. `changes` is built so an untouched note is never sent: an empty
   * string would clear a note the admin wrote earlier, which is a different
   * intent from leaving it alone.
   */
  const triageComplaint = async (complaint, changes) => {
    setSavingComplaint(complaint.id);
    try {
      await updateAdminComplaint(token, complaint.id, changes);
      onNotice(
        `Complaint ${complaint.id} for ${complaint.project_id} → ${changes.status || "note saved"}`,
      );
      setDraftNotes((d) => ({ ...d, [complaint.id]: "" }));
      setComplaints(
        await fetchAdminComplaints(token, { status: complaintFilter || undefined }),
      );
    } catch (e) {
      onNotice(`Error: ${e.message || "update failed"}`);
    } finally {
      setSavingComplaint(null);
    }
  };

  const saveComplaintNote = (complaint) => {
    const draft = (draftNotes[complaint.id] ?? "").trim();
    // Only a change to the stored note is worth a request.
    if (draft === (complaint.admin_note || "")) return;
    triageComplaint(complaint, { admin_note: draft });
  };

  const removeDoc = async (doc) => {
    setRemovingDoc(doc.id);
    try {
      await deleteAdminDocument(token, doc.id);
      onNotice(`Removed ${doc.filename}`);
      setDocs(await fetchAdminDocuments(token));
    } catch (e) {
      onNotice(`Error: ${e.message || "delete failed"}`);
    } finally {
      setRemovingDoc(null);
    }
  };

  const visibleRows = publicRows;
  const hiddenCount = hiddenTotal;
  const canPrev = rowOffset > 0;
  const canNext = rowOffset + PAGE_SIZE < rowTotal;

  return (
    <div className="space-y-6">
      {/* 1. Public directory visibility */}
      <Card
        icon={<Globe className="h-4 w-4 text-brand" />}
        title="Public directory visibility"
        subtitle="Choose which projects the anonymous portal may show, and edit the public summary."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-4" />
              <input
                value={rowSearch}
                onChange={(e) => {
                  setRowSearch(e.target.value);
                  setRowOffset(0);
                }}
                placeholder="Project ID, ministry, sector…"
                className={`${inputCls} w-56 pl-8 py-1.5 text-xs`}
              />
            </div>
            <select
              value={rowFilter}
              onChange={(e) => {
                setRowFilter(e.target.value);
                setRowOffset(0);
              }}
              className="rounded-lg border border-line bg-page px-2 py-1.5 text-xs"
            >
              <option value="all">All</option>
              <option value="public">Published</option>
              <option value="hidden">Hidden ({hiddenCount})</option>
            </select>
          </div>
        }
      >
        <div className="max-h-[26rem] overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 border-b border-line bg-raised text-xs uppercase tracking-wide text-fg-4">
              <tr>
                <th className="px-5 py-2.5 font-medium">Project</th>
                <th className="px-5 py-2.5 font-medium">Public summary</th>
                <th className="px-5 py-2.5 font-medium">Portal</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {visibleRows.map((r) => (
                <tr key={r.project_id} className="transition-colors hover:bg-page">
                  <td className="px-5 py-3 align-top">
                    <p className="font-mono text-xs font-semibold text-fg">{r.project_id}</p>
                    <p className="mt-0.5 text-xs text-fg-3">{r.ministry}</p>
                    <p className="text-[11px] text-fg-4">
                      {r.sector} · {r.status} · {Math.round(r.completion_percent)}%
                    </p>
                  </td>
                  <td className="px-5 py-3 align-top">
                    <textarea
                      value={r.public_summary || ""}
                      onChange={(e) =>
                        setPublicRows((rows) =>
                          rows.map((x) =>
                            x.project_id === r.project_id
                              ? { ...x, public_summary: e.target.value }
                              : x,
                          ),
                        )
                      }
                      rows={2}
                      className={`${inputCls} text-xs`}
                      placeholder="Shown on the public directory…"
                    />
                    <button
                      type="button"
                      onClick={() => saveSummary(r)}
                      disabled={savingRow === r.project_id}
                      className={`mt-1.5 ${btnGhost}`}
                    >
                      Save summary
                    </button>
                  </td>
                  <td className="px-5 py-3 align-top">
                    <span
                      className={`inline-block rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
                        r.is_public_visible
                          ? "border-risk-low-border bg-risk-low-subtle text-risk-low"
                          : "border-line bg-sunken text-fg-4"
                      }`}
                    >
                      {r.is_public_visible ? "Published" : "Hidden"}
                    </span>
                    <button
                      type="button"
                      onClick={() => toggleVisibility(r)}
                      disabled={savingRow === r.project_id}
                      className={`mt-1.5 block w-full ${r.is_public_visible ? btnGhost : btnPrimary}`}
                    >
                      {r.is_public_visible ? "Hide" : "Publish"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {visibleRows.length === 0 && <Empty>No public-directory rows match this filter.</Empty>}
        </div>
        {rowTotal > PAGE_SIZE && (
          <footer className="flex items-center justify-between gap-3 border-t border-line px-5 py-2.5">
            <p className="text-[11px] text-fg-4">
              Showing {rowTotal === 0 ? 0 : rowOffset + 1}–
              {Math.min(rowOffset + PAGE_SIZE, rowTotal)} of {rowTotal.toLocaleString()}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setRowOffset(Math.max(0, rowOffset - PAGE_SIZE))}
                disabled={!canPrev}
                className={btnGhost}
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setRowOffset(rowOffset + PAGE_SIZE)}
                disabled={!canNext}
                className={btnGhost}
              >
                Next
              </button>
            </div>
          </footer>
        )}
      </Card>

      {/* 2. Data operations */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          icon={<Database className="h-4 w-4 text-brand" />}
          title="Data operations"
          subtitle="Row counts per table and live system metadata."
        >
          {!ops ? (
            <Empty>Status unavailable.</Empty>
          ) : (
            <div className="p-5">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
                {Object.entries(ops.table_counts).map(([table, count]) => (
                  <div key={table} className="flex items-baseline justify-between gap-2 border-b border-line pb-1.5">
                    <dt className="truncate font-mono text-fg-3">{table}</dt>
                    <dd className="shrink-0 font-bold text-fg">{count.toLocaleString()}</dd>
                  </div>
                ))}
              </dl>
              {ops.meta.length > 0 && (
                <div className="mt-4 space-y-1.5">
                  {ops.meta.map((m) => (
                    <p key={m.key} className="text-[11px] text-fg-3">
                      <span className="font-mono text-fg-4">{m.key}</span>
                      <span className="mx-1.5">·</span>
                      <span className="text-fg-2">{m.value}</span>
                    </p>
                  ))}
                </div>
              )}
              <button
                type="button"
                onClick={runSeed}
                disabled={seeding}
                className={`mt-4 flex items-center gap-2 ${btnPrimary}`}
              >
                <RefreshCw size={14} className={seeding ? "animate-spin" : ""} />
                {seeding ? "Re-seeding…" : "Re-seed database & retrain models"}
              </button>
              <p className="mt-2 text-[11px] leading-relaxed text-fg-4">
                Retrains the model artifacts and rebuilds the public projection. Destructive —
                existing project, snapshot and prediction rows are replaced.
              </p>
            </div>
          )}
        </Card>

        {/* 3. Model health */}
        <Card
          icon={<Cpu className="h-4 w-4 text-brand" />}
          title="Model registry health"
          subtitle="Which artifacts exist on disk, and which are live in memory."
        >
          {!health ? (
            <Empty>Model status unavailable.</Empty>
          ) : (
            <div className="p-5">
              <div className="flex flex-wrap gap-2">
                <StatusPill
                  ok={health.models_loaded}
                  label={health.models_loaded ? "Registry loaded" : "Registry not loaded"}
                />
                <StatusPill
                  ok={health.extra_models_loaded}
                  label={health.extra_models_loaded ? "Optional models loaded" : "No optional models"}
                />
                <StatusPill
                  ok={health.comparison_metrics_available}
                  label={health.comparison_metrics_available ? "Benchmark metrics" : "No benchmark metrics"}
                />
                <StatusPill
                  ok={health.rag_index_available}
                  label={health.rag_index_available ? "RAG index" : "No RAG index"}
                />
              </div>
              <p className="mt-3 flex items-start gap-1.5 break-all text-[11px] text-fg-4">
                <HardDrive size={12} className="mt-0.5 shrink-0" />
                <span className="font-mono">{health.model_dir}</span>
              </p>
              <div className="mt-3 max-h-56 overflow-auto rounded-xl border border-line">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-raised text-[10px] uppercase tracking-wide text-fg-4">
                    <tr>
                      <th className="px-3 py-2 font-medium">Artifact</th>
                      <th className="px-3 py-2 font-medium">Size</th>
                      <th className="px-3 py-2 font-medium">In memory</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {health.artifacts.map((a) => (
                      <tr key={a.name}>
                        <td className="px-3 py-1.5 font-mono text-fg-2">{a.name}</td>
                        <td className="px-3 py-1.5 text-fg-4">{kb(a.size_bytes)}</td>
                        <td className="px-3 py-1.5">
                          {a.loaded_in_memory ? (
                            <CheckCircle2 size={13} className="text-risk-low" />
                          ) : (
                            <span className="text-fg-4">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* 4. Milestone triage + 5. document review */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          icon={<Activity className="h-4 w-4 text-brand" />}
          title="Milestone triage"
          subtitle="Platform-wide submissions. Ministries normally decide their own queue; this is the escalation path."
          actions={
            <select
              value={subFilter}
              onChange={(e) => setSubFilter(e.target.value)}
              className="rounded-lg border border-line bg-page px-2 py-1.5 text-xs"
            >
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="">All</option>
            </select>
          }
        >
          <div className="max-h-80 divide-y divide-line overflow-auto">
            {subs.map((s) => (
              <div key={s.id} className="px-5 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-fg">{s.title}</p>
                    <p className="font-mono text-[11px] text-fg-3">{s.project_id}</p>
                    {s.description && (
                      <p className="mt-1 line-clamp-2 text-xs text-fg-3">{s.description}</p>
                    )}
                    <p className="mt-1 text-[11px] text-fg-4">
                      {s.budget_spent_crore != null && `${s.budget_spent_crore} Cr spent · `}
                      {s.flagged_delay > 0 ? `${s.flagged_delay} mo delay flagged · ` : ""}
                      {s.submitted_at || "—"}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize ${
                      s.status === "approved"
                        ? "border-risk-low-border bg-risk-low-subtle text-risk-low"
                        : s.status === "rejected"
                          ? "border-risk-critical-border bg-risk-critical-subtle text-risk-critical"
                          : "border-risk-medium-border bg-risk-medium-subtle text-risk-medium"
                    }`}
                  >
                    {s.status}
                  </span>
                </div>
                {s.status === "pending" && (
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => decide(s, true)}
                      disabled={deciding === s.id}
                      className="flex items-center gap-1.5 rounded-lg bg-risk-low px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      <CheckCircle2 size={13} /> Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => decide(s, false)}
                      disabled={deciding === s.id}
                      className="flex items-center gap-1.5 rounded-lg bg-risk-critical px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      <XCircle size={13} /> Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
            {subs.length === 0 && <Empty>No submissions in this state.</Empty>}
          </div>
        </Card>

        <Card
          icon={<FileWarning className="h-4 w-4 text-brand" />}
          title="Proof document review"
          subtitle="Documents uploaded by agency users, with the uploading account resolved."
        >
          <div className="max-h-80 divide-y divide-line overflow-auto">
            {docs.map((d) => (
              <div key={d.id} className="flex items-center justify-between gap-3 px-5 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-fg">{d.filename}</p>
                  <p className="font-mono text-[11px] text-fg-3">
                    {d.project_id}
                    {d.milestone_id ? ` · milestone #${d.milestone_id}` : ""}
                  </p>
                  <p className="text-[11px] text-fg-4">
                    {d.uploaded_by || "unknown uploader"} · {d.uploaded_at || "—"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {d.url && (
                    <a
                      href={d.url}
                      target="_blank"
                      rel="noreferrer"
                      className={btnGhost}
                    >
                      Open
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => removeDoc(d)}
                    disabled={removingDoc === d.id}
                    className="flex items-center gap-1.5 rounded-lg bg-risk-critical px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    <Trash2 size={13} /> Remove
                  </button>
                </div>
              </div>
            ))}
            {docs.length === 0 && (
              <Empty>No documents uploaded. Agencies attach these to milestone submissions.</Empty>
            )}
          </div>
        </Card>
      </div>

      {/* 6. Risk signals + message thread */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          icon={<Tags className="h-4 w-4 text-brand" />}
          title="Risk-signal remarks"
          subtitle="Warning tags extracted from snapshot remarks text, with the owning ministry."
        >
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 border-b border-line bg-raised text-[10px] uppercase tracking-wide text-fg-4">
                <tr>
                  <th className="px-5 py-2 font-medium">Tag</th>
                  <th className="px-5 py-2 font-medium">Project</th>
                  <th className="px-5 py-2 font-medium">Conf.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {signals.map((s) => (
                  <tr key={s.id} className="transition-colors hover:bg-page">
                    <td className="px-5 py-2">
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-risk-medium-border bg-risk-medium-subtle px-2.5 py-0.5 text-[11px] font-semibold text-risk-medium">
                        <AlertTriangle size={11} />
                        {s.tag}
                      </span>
                    </td>
                    <td className="px-5 py-2">
                      <p className="font-mono text-fg-2">{s.project_id}</p>
                      <p className="text-[11px] text-fg-4">{s.ministry}</p>
                    </td>
                    <td className="px-5 py-2 text-fg-3">
                      {s.confidence != null ? `${Math.round(s.confidence * 100)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {signals.length === 0 && (
              <Empty>
                No extracted signals. These are produced by the remarks pipeline during seeding.
              </Empty>
            )}
          </div>
        </Card>

        <Card
          icon={<MessageSquare className="h-4 w-4 text-brand" />}
          title="Ministry ↔ agency thread"
          subtitle="Messages exchanged on project records, flattened for oversight."
        >
          <div className="max-h-72 divide-y divide-line overflow-auto">
            {notes.map((n) => (
              <div key={n.id} className="px-5 py-3">
                <p className="text-xs text-fg-2">{n.text}</p>
                <p className="mt-1 text-[11px] text-fg-4">
                  <span className="font-mono">{n.project_id}</span>
                  <span className="mx-1.5">·</span>
                  {n.sender_email || n.sender_role || "unknown"}
                  <span className="mx-1.5">·</span>
                  {n.created_at || "—"}
                </p>
              </div>
            ))}
            {notes.length === 0 && <Empty>No messages on record.</Empty>}
          </div>
        </Card>

        <Card
          icon={<MessageSquareWarning className="h-4 w-4 text-brand" />}
          title="Public complaint queue"
          subtitle="Anonymous reports that a published figure looks wrong. Email is shown only when the visitor chose to give one."
          actions={
            <select
              value={complaintFilter}
              onChange={(e) => setComplaintFilter(e.target.value)}
              className="rounded-lg border border-line bg-page px-2 py-1.5 text-xs"
            >
              <option value="new">New</option>
              <option value="reviewing">Reviewing</option>
              <option value="resolved">Resolved</option>
              <option value="rejected">Rejected</option>
              <option value="">All</option>
            </select>
          }
        >
          <div className="max-h-96 divide-y divide-line overflow-auto">
            {complaints.map((c) => (
              <div key={c.id} className="px-5 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-fg">
                      {c.subject || "(no summary given)"}
                    </p>
                    <p className="font-mono text-[11px] text-fg-3">
                      #{c.id} · {c.project_id}
                      {c.ministry ? ` · ${c.ministry}` : ""}
                    </p>
                    <p className="mt-1 whitespace-pre-line text-xs leading-relaxed text-fg-2">
                      {c.description}
                    </p>
                    <p className="mt-1.5 text-[11px] text-fg-4">
                      <span className="font-semibold capitalize">{c.category.replace(/_/g, " ")}</span>
                      <span className="mx-1.5">·</span>
                      {c.reporter_email || "anonymous"}
                      <span className="mx-1.5">·</span>
                      {c.created_at || "—"}
                      {c.resolved_at ? ` · closed ${c.resolved_at}` : ""}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize ${
                      c.status === "resolved"
                        ? "border-risk-low-border bg-risk-low-subtle text-risk-low"
                        : c.status === "rejected"
                          ? "border-risk-critical-border bg-risk-critical-subtle text-risk-critical"
                          : c.status === "reviewing"
                            ? "border-brand-border bg-brand-subtle text-brand-subtle-fg"
                            : "border-risk-medium-border bg-risk-medium-subtle text-risk-medium"
                    }`}
                  >
                    {c.status}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {c.status !== "new" && (
                    <button
                      type="button"
                      disabled={savingComplaint === c.id}
                      onClick={() => triageComplaint(c, { status: "reviewing" })}
                      className={btnGhost}
                    >
                      Reopen
                    </button>
                  )}
                  {c.status !== "resolved" && (
                    <button
                      type="button"
                      disabled={savingComplaint === c.id}
                      onClick={() => triageComplaint(c, { status: "resolved" })}
                      className="flex items-center gap-1.5 rounded-lg bg-risk-low px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      <CheckCircle2 size={13} /> Resolve
                    </button>
                  )}
                  {c.status !== "rejected" && (
                    <button
                      type="button"
                      disabled={savingComplaint === c.id}
                      onClick={() => triageComplaint(c, { status: "rejected" })}
                      className="flex items-center gap-1.5 rounded-lg bg-risk-critical px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      <XCircle size={13} /> Reject
                    </button>
                  )}
                </div>

                <div className="mt-2">
                  <label
                    htmlFor={`cn-${c.id}`}
                    className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-fg-4"
                  >
                    Internal note
                  </label>
                  <textarea
                    id={`cn-${c.id}`}
                    rows={2}
                    maxLength={2000}
                    defaultValue={c.admin_note || ""}
                    onChange={(e) =>
                      setDraftNotes((d) => ({ ...d, [c.id]: e.target.value }))
                    }
                    onBlur={() => saveComplaintNote(c)}
                    placeholder="Not shown to the reporter. Saved on blur."
                    className="w-full rounded-lg border border-line bg-page px-3 py-2 text-xs text-fg outline-none focus:border-brand"
                  />
                  {c.admin_note && !(c.id in draftNotes) && (
                    <p className="mt-1 text-[10px] text-fg-4">Last note saved.</p>
                  )}
                </div>
              </div>
            ))}
            {complaints.length === 0 && (
              <Empty>No complaints in this state.</Empty>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function StatusPill({ ok, label }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
        ok
          ? "border-risk-low-border bg-risk-low-subtle text-risk-low"
          : "border-line bg-sunken text-fg-4"
      }`}
    >
      {ok ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
      {label}
    </span>
  );
}
