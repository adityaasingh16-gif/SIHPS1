import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Flag,
  Info,
  Loader2,
  Search,
  Send,
} from "lucide-react";

import { LANGUAGES, translate } from "./i18n";
import {
  fetchComplaintCategories,
  fetchPublicProjectPage,
  submitPublicComplaint,
} from "./api";
import {
  PublicFooter,
  PublicMasthead,
  PublicNav,
  PublicUtilityBar,
} from "./components/public/PublicChrome";

const inputCls =
  "w-full rounded-xl border border-line bg-page px-3.5 py-2.5 text-sm outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/40";

/** How many project options to offer before the visitor has to type. */
const PROJECT_SUGGESTION_LIMIT = 400;

/**
 * Anonymous "report an issue" form.
 *
 * The project field is a plain text input with a datalist rather than a
 * <select>: the directory holds 2,185 projects, so a dropdown is unusable,
 * and `fetchPublicProjects` already pages the list. Datalist filtering is
 * the browser's, so typing narrows the suggestions without a request.
 */
export function ReportIssuePage({
  language,
  setLanguage,
  onLogin,
  loggedInUser,
  onLogout,
}) {
  const t = useMemo(() => (key) => translate(language, key), [language]);

  const [projects, setProjects] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loadingLists, setLoadingLists] = useState(true);

  const [projectId, setProjectId] = useState("");
  const [category, setCategory] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState(loggedInUser?.email || "");
  const [website, setWebsite] = useState("");

  const [sending, setSending] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [error, setError] = useState(null);

  // Both lists come from the backend: categories because the router owns the
  // whitelist, projects because the portal may not publish all of them.
  useEffect(() => {
    let alive = true;
    Promise.all([
      fetchComplaintCategories().catch(() => []),
      fetchPublicProjectPage({ limit: PROJECT_SUGGESTION_LIMIT })
        .then((d) => d.rows)
        .catch(() => []),
    ]).then(([cats, rows]) => {
      if (!alive) return;
      setCategories(Array.isArray(cats) ? cats : []);
      setProjects(Array.isArray(rows) ? rows : []);
      setLoadingLists(false);
    });
    return () => {
      alive = false;
    };
  }, []);

  // Deep link support: /report-an-issue?project=108841 pre-fills the field.
  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("project");
    if (wanted) setProjectId(wanted);
  }, []);

  const navItems = useMemo(
    () => [
      { id: "home", label: t("public.home"), href: "/" },
      { id: "directory", label: t("public.directory"), href: "/projects" },
      { id: "reports", label: t("public.reports"), href: "/reports" },
    ],
    [t],
  );

  const selected = projects.find((p) => p.project_id === projectId);

  const reset = () => {
    setProjectId("");
    setCategory("");
    setSubject("");
    setDescription("");
    setEmail("");
    setWebsite("");
    setReceipt(null);
    setError(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!projectId.trim()) return setError("Choose the project this is about.");
    if (!category) return setError("Choose what looks wrong.");
    if (description.trim().length < 10)
      return setError("Please add a little more detail — at least 10 characters.");

    setSending(true);
    try {
      const res = await submitPublicComplaint({
        project_id: projectId.trim(),
        category,
        subject: subject.trim() || undefined,
        description: description.trim(),
        reporter_email: email.trim() || undefined,
        website: website || undefined,
      });
      setReceipt(res.reference);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err.message || "Could not send your report.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-h-screen bg-page font-sans">
      <PublicUtilityBar
        language={language}
        setLanguage={setLanguage}
        languages={LANGUAGES}
        t={t}
      />
      <PublicMasthead
        loggedInUser={loggedInUser}
        onLogin={onLogin}
        onLogout={onLogout}
        onOpenDirectory={() => {}}
        t={t}
      />
      <PublicNav items={navItems} activeId="home" onSelect={() => {}} t={t} />

      <main className="mx-auto max-w-3xl px-4 py-10 md:px-6 md:py-14">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-fg-3 transition-colors hover:text-brand"
        >
          ← Back to portal
        </Link>

        {receipt ? (
          <div className="mt-8 rounded-2xl border border-risk-low-border bg-risk-low-subtle px-6 py-8 text-center">
            <CheckCircle2 size={30} className="mx-auto text-risk-low" />
            <h1 className="mt-4 text-lg font-extrabold text-fg">{t("report.sentTitle")}</h1>
            <p className="mt-2 text-sm text-fg-2">{t("report.sentBody")}</p>
            <p className="mt-5 inline-block rounded-lg border border-line bg-page px-5 py-2.5 font-mono text-lg font-bold text-fg">
              {receipt}
            </p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <button
                type="button"
                onClick={reset}
                className="rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-hover"
              >
                {t("report.sendAnother")}
              </button>
              <Link
                to="/projects"
                className="rounded-lg border border-line bg-page px-4 py-2.5 text-sm font-semibold text-fg-2 transition-colors hover:border-brand hover:text-brand"
              >
                {t("public.directory")}
              </Link>
            </div>
          </div>
        ) : (
          <>
            <header className="mt-6">
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-subtle text-brand-subtle-fg">
                <Flag size={20} />
              </span>
              <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-fg md:text-3xl">
                {t("report.title")}
              </h1>
              <p className="mt-2.5 text-sm leading-relaxed text-fg-3">{t("report.intro")}</p>
            </header>

            <form
              onSubmit={submit}
              className="mt-8 space-y-5 rounded-2xl border border-line bg-raised p-5 md:p-7"
            >
              <div>
                <label htmlFor="rp-project" className="mb-1.5 block text-xs font-semibold text-fg-2">
                  {t("report.project")}
                </label>
                <div className="relative">
                  <Search
                    size={15}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-4"
                  />
                  <input
                    id="rp-project"
                    list="project-options"
                    required
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value.trim())}
                    placeholder={t("report.searchProject")}
                    className={`${inputCls} pl-9`}
                  />
                  <datalist id="project-options">
                    {projects.map((p) => (
                      <option key={p.project_id} value={p.project_id}>
                        {p.ministry} · {p.status}
                      </option>
                    ))}
                  </datalist>
                </div>
                {selected ? (
                  <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-fg-3">
                    <span className="font-semibold text-fg-2">{selected.ministry}</span>
                    <span>·</span>
                    <span>{selected.sector}</span>
                    <span>·</span>
                    <span>{selected.status}</span>
                    <span>·</span>
                    <span>{Math.round(selected.completion_percent)}% complete</span>
                  </p>
                ) : (
                  <p className="mt-2 text-[11px] text-fg-4">
                    {loadingLists
                      ? "Loading the project list…"
                      : "Type at least part of a project id, or pick one from the list."}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="rp-category" className="mb-1.5 block text-xs font-semibold text-fg-2">
                  {t("report.category")}
                </label>
                <select
                  id="rp-category"
                  required
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className={inputCls}
                >
                  <option value="">{t("report.pickCategory")}</option>
                  {categories.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="rp-subject" className="mb-1.5 block text-xs font-semibold text-fg-2">
                  {t("report.subject")}{" "}
                  <span className="font-normal text-fg-4">(optional)</span>
                </label>
                <input
                  id="rp-subject"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  maxLength={255}
                  placeholder={t("report.subjectPlaceholder")}
                  className={inputCls}
                />
              </div>

              <div>
                <label htmlFor="rp-description" className="mb-1.5 block text-xs font-semibold text-fg-2">
                  {t("report.description")}
                </label>
                <textarea
                  id="rp-description"
                  required
                  rows={5}
                  minLength={10}
                  maxLength={4000}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("report.descriptionPlaceholder")}
                  className={`${inputCls} resize-y leading-relaxed`}
                />
                <p className="mt-1.5 text-right text-[11px] tabular-nums text-fg-4">
                  {description.length} / 4000
                </p>
              </div>

              <div>
                <label htmlFor="rp-email" className="mb-1.5 block text-xs font-semibold text-fg-2">
                  {t("report.email")}
                </label>
                <input
                  id="rp-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className={inputCls}
                />
                <p className="mt-1.5 flex items-start gap-1.5 text-[11px] text-fg-4">
                  <Info size={12} className="mt-0.5 shrink-0" />
                  {t("report.emailHint")}
                </p>
              </div>

              {/* Honeypot. Hidden from people, filled by naive bots. */}
              <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
                <label htmlFor="rp-website">{t("report.website")}</label>
                <input
                  id="rp-website"
                  name="website"
                  type="text"
                  tabIndex={-1}
                  autoComplete="off"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                />
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-xl border border-risk-critical-border bg-risk-critical-subtle px-4 py-3 text-sm text-risk-critical">
                  <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                  {error}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-4 border-t border-line pt-5">
                <button
                  type="submit"
                  disabled={sending}
                  className="flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-hover disabled:opacity-50"
                >
                  {sending ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Send size={15} />
                  )}
                  {sending ? t("report.sending") : t("report.submit")}
                </button>
                <p className="flex items-center gap-1.5 text-[11px] text-fg-4">
                  <Info size={12} />
                  {t("report.reviewNote")}
                </p>
              </div>
            </form>
          </>
        )}
      </main>

      <PublicFooter t={t} />
    </div>
  );
}
