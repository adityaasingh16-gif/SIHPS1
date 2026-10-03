import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  CheckCircle2,
  Flag,
  Search,
  ShieldCheck,
  TrendingDown,
} from "lucide-react";
import { LANGUAGES, translate } from "./i18n";
import { fetchHighValueProjects, fetchPublicProjectPage, fetchPublicSummary } from "./api";
import { CompactStat } from "./components/ui/HeroKPI";
import { HeroSlideshow } from "./components/public/HeroSlideshow";
import { HighValueRail } from "./components/public/HighValueRail";
import JarvisPopup from "./JarvisPopup";
import {
  DhrishtiMark,
  PublicFooter,
  PublicMasthead,
  PublicNav,
  PublicUtilityBar,
} from "./components/public/PublicChrome";

const NAVY = "#0a154d";

/** Rows fetched per request. The backend caps `limit` at 500. */
const PAGE_SIZE = 200;

const TIER_COLORS = {
  Critical: "bg-risk-critical-subtle text-risk-critical border-risk-critical-border",
  High: "bg-risk-high-subtle text-risk-high border-risk-high-border",
  Medium: "bg-risk-medium-subtle text-risk-medium border-risk-medium-border",
  Low: "bg-risk-low-subtle text-risk-low border-risk-low-border",
};

/**
 * Ranks a `{ label: count }` map from `/public/summary` into the top `n`
 * shares, with each share expressed as a percentage of the whole portfolio
 * rather than of the top slice — otherwise every bar looks like a fifth of the
 * bar above it and the chart communicates nothing.
 */
function topOf(counts, n) {
  if (!counts) return [];
  const entries = Object.entries(counts)
    .map(([name, count]) => [name, Number(count) || 0])
    .sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, c]) => sum + c, 0) || 1;
  return entries
    .slice(0, n)
    .map(([name, count]) => ({
      name,
      count,
      pct: Math.round((count / total) * 100),
    }));
}

/** Section heading in the portal's style: uppercase, heavy, centred. */
function SectionHead({ title, blurb, id }) {
  return (
    <div className="mb-6 text-center">
      <h2
        id={id}
        className="text-[22px] font-extrabold uppercase tracking-tight text-[#060e37] md:text-[26px] dark:text-white"
      >
        {title}
      </h2>
      {blurb && (
        <p className="mx-auto mt-2 max-w-2xl text-[12px] leading-relaxed text-fg-3">
          {blurb}
        </p>
      )}
      <span
        aria-hidden="true"
        className="mx-auto mt-3 block h-1 w-16 rounded-full"
        style={{ backgroundColor: NAVY }}
      />
    </div>
  );
}

export default function PublicDirectory({
  language,
  setLanguage,
  onLogin,
  loggedInUser,
  onLogout,
}) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(null);
  const [summary, setSummary] = useState(null);
  const [cards, setCards] = useState([]);
  const [cardsLoading, setCardsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [onTrack, setOnTrack] = useState();
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [activeNav, setActiveNav] = useState("high-value");
  // The assistants read this to show "offline" instead of an empty alert list,
  // so it comes from the one request this page already makes.
  const [loadFailed, setLoadFailed] = useState(false);

  const navigate = useNavigate();
  const goToLens = (id) => navigate(id === "dashboard" ? "/" : `/${id}`);

  const t = useMemo(() => (key) => translate(language, key), [language]);

  // `append` distinguishes "Load more" (accumulate the next page) from a
  // filter change, which must replace the table rather than add to it.
  // `offset` is passed in rather than read from `rows` so that appending never
  // depends on a `rows` value captured by an older render.
  const load = async (s, tr, { offset = 0, append = false } = {}) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const [page, sum] = await Promise.all([
        fetchPublicProjectPage({
          search: s || undefined,
          on_track: tr === undefined ? undefined : tr,
          limit: PAGE_SIZE,
          offset,
        }),
        append ? Promise.resolve(null) : fetchPublicSummary(),
      ]);
      setRows((prev) => (append ? [...prev, ...page.rows] : page.rows));
      setTotal(page.total);
      if (sum) setSummary(sum);
      setLoadFailed(false);
    } catch (e) {
      console.warn("Public directory load failed:", e);
      setLoadFailed(true);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // A visitor may land on `/#high-value` or `/#directory` via a shared anchor
  // link; scroll them to the section once the page has mounted.
  useEffect(() => {
    const id = window.location.hash.replace("#", "");
    if (id && document.getElementById(id)) {
      document.getElementById(id).scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveNav(id);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => load(search, onTrack, { offset: 0 }), 350);
    return () => clearTimeout(timer);
  }, [search, onTrack]);

  // Card rail is independent of the directory's search/filter state, so it
  // loads once. Failures degrade to an empty rail rather than an error state.
  useEffect(() => {
    let cancelled = false;
    fetchHighValueProjects({ limit: 14 })
      .then((data) => {
        if (!cancelled) setCards(data || []);
      })
      .catch((e) => console.warn("High-value rail load failed:", e))
      .finally(() => {
        if (!cancelled) setCardsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // An `#href` is a native anchor that scrolls to a section on this page; a
  // `/href` is a real route into the read-only feature screens. The bar
  // scrolls horizontally on narrow viewports, so the full set is kept to what
  // a visitor needs to reach every feature without wrapping.
  const navItems = useMemo(
    () => [
      { id: "high-value", label: t("public.highValue"), href: "#high-value" },
      { id: "directory", label: t("public.directory"), href: "#directory" },
      { id: "dashboard", label: t("public.dashboard"), href: "/dashboard" },
      { id: "risk", label: t("public.riskAnalytics"), href: "/risk" },
      { id: "cost", label: t("public.costIntelligence"), href: "/cost" },
      { id: "time", label: t("public.timeIntelligence"), href: "/time" },
      { id: "warnings", label: t("public.earlyWarnings"), href: "/warnings" },
      { id: "projects", label: t("public.project"), href: "/projects" },
      { id: "states", label: t("public.stateWise"), href: "/states" },
      { id: "ministries", label: t("public.ministries"), href: "/ministries" },
      { id: "reports", label: t("public.reports"), href: "/reports" },
      { id: "graph", label: t("public.knowledgeGraph"), href: "/graph" },
      { id: "report", label: t("public.reportIssue"), href: "/report-an-issue" },
    ],
    [t],
  );

  const sectorBars = useMemo(
    () => topOf(summary?.sector_counts, 7),
    [summary],
  );

  const ministryBars = useMemo(
    () => topOf(summary?.ministry_counts, 7),
    [summary],
  );

  const scrollTo = (item) => {
    setActiveNav(item.id);
    const el = document.getElementById(item.id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      const hash = `#${item.id}`;
      if (window.location.hash !== hash) window.history.replaceState(null, "", hash);
    }
  };

  return (
    <div
      id="top"
      className="min-h-screen bg-page font-sans"
      style={{ backgroundImage: "linear-gradient(180deg, var(--surface-sunken), var(--surface-page) 460px)" }}
    >
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
        onOpenDirectory={() => scrollTo(navItems[1])}
        t={t}
      />

      <PublicNav
        items={navItems}
        activeId={activeNav}
        onSelect={scrollTo}
        t={t}
      />

      <main id="main-content">
        {/* Hero. The portal leads with a full-bleed photo slide show of major
            infrastructure under way — rail, metro, highways, ports, water —
            crossfading behind the same navy treatment that keeps the copy
            readable over any frame. */}
        <section
          className="relative flex min-h-[440px] items-center overflow-hidden"
          style={{ backgroundImage: `linear-gradient(135deg, ${NAVY}, #060e37)` }}
          aria-label={t("public.title")}
        >
          <HeroSlideshow t={t} />

          <div className="relative z-10 mx-auto max-w-[1320px] px-4 py-16 text-center md:py-24">
            <div className="flex justify-center">
              <span className="rounded-2xl bg-white/95 px-6 py-4 shadow-pop">
                <DhrishtiMark className="h-11" t={t} onLight />
              </span>
            </div>

            <h1 className="mt-7 text-[28px] font-extrabold uppercase leading-tight tracking-tight text-white md:text-[44px]">
              {t("public.projectMonitoring")}
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-[13px] leading-relaxed text-white/65">
              {t("public.heroMonitoring")}
            </p>
          </div>
        </section>

        {/* Portfolio split */}
        <section className="mx-auto max-w-[1320px] px-4">
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <CompactStat
              icon={Activity}
              label={t("public.total")}
              value={summary?.total_projects ?? "—"}
              subtitle={t("public.title")}
              hue="violet"
              tone="solid"
            />
            <CompactStat
              icon={CheckCircle2}
              label={t("public.onTrack")}
              value={summary?.on_track_count ?? "—"}
              subtitle={t("public.avgCompletion")}
              hue="emerald"
              tone="solid"
            />
            <CompactStat
              icon={TrendingDown}
              label={t("public.delayed")}
              value={summary?.delayed_count ?? "—"}
              subtitle={t("public.delayed")}
              hue="rose"
              tone="solid"
            />
            <CompactStat
              icon={ShieldCheck}
              label={t("public.avgCompletion")}
              value={summary ? `${summary.avg_completion_percent}%` : "—"}
              subtitle={t("app.subtitle")}
              hue="cyan"
              tone="solid"
            />
          </div>
        </section>

        {/* Sector mix + leading ministries. Both come straight from
            `/public/summary`, so they stay in step with the counts above
            instead of being derived client-side from a page of rows. */}
        <section className="mx-auto max-w-[1320px] px-4 pt-14">
          <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
            <div className="rounded-[20px] border border-line-strong bg-raised p-6 shadow-card">
              <h2 className="text-[14px] font-bold uppercase tracking-widest text-fg-2">
                {t("public.sectorMix")}
              </h2>
              {sectorBars.length === 0 ? (
                <p className="mt-4 text-sm text-fg-4">—</p>
              ) : (
                <ul className="mt-5 space-y-3">
                  {sectorBars.map((s) => (
                    <li key={s.name}>
                      <div className="flex items-baseline justify-between gap-3 text-[12px]">
                        <span className="truncate font-semibold text-fg-2">
                          {s.name}
                        </span>
                        <span className="shrink-0 tabular-nums text-fg-3">
                          {s.count} · {s.pct}%
                        </span>
                      </div>
                      <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-sunken">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.max(s.pct, 1)}%`,
                            backgroundColor: NAVY,
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-[20px] border border-line-strong bg-raised p-6 shadow-card">
              <h2 className="text-[14px] font-bold uppercase tracking-widest text-fg-2">
                {t("public.ministryMix")}
              </h2>
              {ministryBars.length === 0 ? (
                <p className="mt-4 text-sm text-fg-4">—</p>
              ) : (
                <ul className="mt-5 space-y-2.5">
                  {ministryBars.map((m) => (
                    <li
                      key={m.name}
                      className="flex items-center justify-between gap-3 border-b border-line pb-2.5 text-[12px] last:border-0 last:pb-0"
                    >
                      <span className="truncate font-semibold text-fg-2">
                        {m.name}
                      </span>
                      <span
                        className="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold tabular-nums"
                        style={{ backgroundColor: NAVY, color: "#fff" }}
                      >
                        {m.count}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </section>

        {/* High Value Projects */}
        <section id="high-value" className="mx-auto max-w-[1320px] scroll-mt-20 px-4 pt-14">
          <SectionHead
            title={t("public.highValue")}
            blurb={t("public.highValueBlurb")}
          />
          <HighValueRail
            projects={cards}
            loading={cardsLoading}
            t={t}
          />
        </section>

        {/* Project Directory */}
        <section id="directory" className="mx-auto max-w-[1320px] scroll-mt-20 px-4 pt-14">
          <SectionHead
            title={t("public.directory")}
            blurb={t("public.directoryBlurb")}
          />

          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-4" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("public.search")}
                className="w-full rounded-full border border-line-strong bg-raised py-2.5 pl-9 pr-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/40"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <FilterChip
                active={onTrack === undefined}
                onClick={() => setOnTrack(undefined)}
                label={`${t("public.filter")}: ${t("public.total")}`}
              />
              <FilterChip
                active={onTrack === 1}
                onClick={() => setOnTrack(1)}
                label={t("public.onTrack")}
              />
              <FilterChip
                active={onTrack === 0}
                onClick={() => setOnTrack(0)}
                label={t("public.delayed")}
              />
            </div>
          </div>

          <div className="overflow-hidden rounded-[20px] border border-line-strong bg-raised shadow-card">
            <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
              <h3 className="text-[12px] font-bold uppercase tracking-widest text-fg-2">
                {t("public.directory")}
              </h3>
              <span className="text-xs text-fg-3">
                {loading
                  ? "..."
                  : `${rows.length}${total !== null ? ` / ${total}` : ""}`}
              </span>
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-line bg-page text-[10px] font-bold uppercase tracking-widest text-fg-3">
                  <tr>
                    <th className="px-5 py-3 font-bold">{t("public.project")}</th>
                    <th className="px-5 py-3 font-bold">{t("public.sector")}</th>
                    <th className="px-5 py-3 font-bold">{t("public.ministry")}</th>
                    <th className="px-5 py-3 font-bold">{t("public.status")}</th>
                    <th className="px-5 py-3 font-bold">
                      {t("public.physicalProgress")}
                    </th>
                    <th className="px-5 py-3 font-bold">{t("public.riskTier")}</th>
                    <th className="px-5 py-3 font-bold">
                      <span className="sr-only">{t("public.reportIssue")}</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.map((r) => (
                    <tr
                      key={r.project_id}
                      className="transition-colors hover:bg-page"
                    >
                      <td className="px-5 py-3 font-semibold text-fg">
                        {r.project_id}
                      </td>
                      <td className="px-5 py-3 text-fg-2">{r.sector}</td>
                      <td className="px-5 py-3 text-fg-2">{r.ministry}</td>
                      <td className="px-5 py-3 text-fg-2">{r.status}</td>
                      <td className="px-5 py-3 tabular-nums text-fg-2">
                        {r.completion_percent}%
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
                            TIER_COLORS[r.risk_tier_label] || TIER_COLORS.Low
                          }`}
                        >
                          {r.risk_tier_label}
                        </span>
                        <span
                          className={`ml-1.5 text-[11px] ${
                            r.on_track ? "text-risk-low" : "text-risk-high"
                          }`}
                        >
                          {r.on_track ? "●" : "◌"}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Link
                          to={`/report-an-issue?project=${encodeURIComponent(r.project_id)}`}
                          className="inline-flex items-center gap-1.5 rounded-full border border-line-strong px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-fg-3 transition-colors hover:border-brand hover:text-brand"
                        >
                          <Flag size={11} />
                          {t("public.reportIssue")}
                        </Link>
                      </td>
                    </tr>
                  ))}
                  {!loading && rows.length === 0 && (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-5 py-10 text-center text-sm text-fg-3"
                      >
                        {t("public.search")}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Card view on phones — the wide table gives way to tappable
                tiles so nobody has to swipe to reach a project. */}
            <ul className="divide-y divide-line md:hidden">
              {rows.map((r) => {
                const tierColors = TIER_COLORS[r.risk_tier_label] || TIER_COLORS.Low;
                return (
                  <li key={r.project_id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-[15px] font-bold text-fg">
                          {r.project_id}
                        </p>
                        <p className="mt-1 text-[12px] leading-snug text-fg-3">
                          {r.sector} · {r.ministry}
                        </p>
                      </div>
                      <Link
                        to={`/report-an-issue?project=${encodeURIComponent(r.project_id)}`}
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-line-strong px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-fg-3 transition-colors hover:border-brand hover:text-brand"
                      >
                        <Flag size={12} />
                        {t("public.reportIssue")}
                      </Link>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-fg-3">
                      <span className="min-w-0 truncate">
                        {t("public.status")}: {r.status}
                      </span>
                      <span className="shrink-0 tabular-nums">
                        {t("public.physicalProgress")}:{" "}
                        <b className="text-fg-2">{r.completion_percent}%</b>
                      </span>
                    </div>
                    <div className="mt-2.5 flex items-center gap-2">
                      <span
                        className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${tierColors}`}
                      >
                        {r.risk_tier_label}
                      </span>
                      <span
                        className={`ml-1 flex items-center gap-1 text-[11px] ${
                          r.on_track ? "text-risk-low" : "text-risk-high"
                        }`}
                      >
                        <span aria-hidden="true">{r.on_track ? "●" : "◌"}</span>
                        {r.on_track ? t("public.onTrack") : t("public.delayed")}
                      </span>
                    </div>
                  </li>
                );
              })}
              {!loading && rows.length === 0 && (
                <li className="px-5 py-10 text-center text-sm text-fg-3">
                  {t("public.search")}
                </li>
              )}
            </ul>
            {!loading && rows.length > 0 && (total === null || rows.length < total) && (
              <div className="flex justify-center border-t border-line px-5 py-4">
                <button
                  type="button"
                  onClick={() =>
                    load(search, onTrack, {
                      offset: rows.length,
                      append: true,
                    })
                  }
                  disabled={loadingMore}
                  className="rounded-full px-6 py-2.5 text-[11px] font-bold uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                  style={{ backgroundColor: NAVY }}
                >
                  {loadingMore ? "..." : t("public.loadMore")}
                </button>
              </div>
            )}
          </div>
        </section>
      </main>

      <PublicFooter t={t} />

      <JarvisPopup backendOnline={!loadFailed} setActive={goToLens} />
    </div>
  );
}

function FilterChip({ active, onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-2 text-[11px] font-bold uppercase tracking-wider transition-colors ${
        active
          ? "text-white"
          : "border border-line-strong bg-raised text-fg-2 hover:bg-page"
      }`}
      style={active ? { backgroundColor: NAVY } : undefined}
    >
      {label}
    </button>
  );
}
