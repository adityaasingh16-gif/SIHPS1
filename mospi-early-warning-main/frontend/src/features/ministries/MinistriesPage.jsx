import { useEffect, useMemo, useState } from "react";
import { Building2, X, Layers, Landmark } from "lucide-react";
import { fetchMinistries } from "../../api";
import { formatCr } from "../../lib/format";
import { PageHeader } from "../../components/ui/PageHeader";
import { Metric } from "../../components/ui/Metric";
import { useT } from "../../hooks/useT";

export { MinistriesPage };

/**
 * Ministry and sector portfolios.
 *
 * Everything here is a server-computed aggregate of the monitored portfolio.
 * There is deliberately no "health" score per card: the source data carries no
 * such measure, and a single invented number per ministry would read as an
 * assessment. The bar shown is the share of projects flagged on-track, and it
 * is labelled as such.
 */
function MinistriesPage() {
  const t = useT();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("ministries");
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchMinistries();
        if (cancelled) return;
        setData(res);
      } catch (err) {
        if (!cancelled) setError(err?.message || t("ministries.loadError"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t]);

  const groups = useMemo(() => {
    if (!data) return [];
    const all = view === "ministries" ? data.ministries : data.sectors;
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (g) =>
        g.name.toLowerCase().includes(q) ||
        g.childSectors.some((s) => s.toLowerCase().includes(q)),
    );
  }, [data, view, query]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-72 animate-pulse rounded bg-raised" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="h-44 animate-pulse rounded-2xl bg-raised" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader
          icon={Building2}
          title={t("ministries.title")}
          subtitle={t("ministries.subtitle")}
        />
        <div className="rounded-2xl border border-risk-high bg-raised p-5 text-sm text-risk-high">
          {error}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const portfolioCost = data.ministries.reduce(
    (sum, m) => sum + (m.totalOriginalCostCrore ?? 0),
    0,
  );
  const isMinistry = view === "ministries";
  const totalOnTrack = data.ministries.reduce((s, m) => s + m.onTrackCount, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Building2}
        title={t("ministries.title")}
        subtitle={t("ministries.pageSubtitle", {
          ministries: data.totalMinistries,
          sectors: data.totalSectors,
          projects: data.totalProjects.toLocaleString(),
        })}
      />

      <div className="grid gap-3 md:grid-cols-4">
        <Metric label={t("common.ministries")} value={data.totalMinistries} />
        <Metric label={t("common.sectors")} value={data.totalSectors} />
        <Metric
          label={t("ministries.portfolioCost")}
          value={formatCr(Math.round(portfolioCost))}
        />
        <Metric
          label={t("ministries.flaggedOnTrack")}
          value={`${totalOnTrack.toLocaleString()} (${data.totalProjects ? Math.round((totalOnTrack / data.totalProjects) * 100) : 0}%)`}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-xl border border-line bg-raised p-1">
          <button
            onClick={() => setView("ministries")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              isMinistry
                ? "bg-brand-subtle text-brand-hover"
                : "text-fg-2 hover:text-fg"
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              <Landmark size={13} /> {t("ministries.tabMinistries", { n: data.totalMinistries })}
            </span>
          </button>
          <button
            onClick={() => setView("sectors")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              !isMinistry
                ? "bg-brand-subtle text-brand-hover"
                : "text-fg-2 hover:text-fg"
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              <Layers size={13} /> {t("ministries.tabSectors", { n: data.totalSectors })}
            </span>
          </button>
        </div>

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={isMinistry ? t("ministries.filterMinistries") : t("ministries.filterSectors")}
          className="min-w-52 rounded-xl border border-line bg-raised px-3 py-1.5 text-xs text-fg"
        />

        {query && (
          <button
            onClick={() => setQuery("")}
            className="text-xs font-semibold text-fg-3 hover:text-fg"
          >
            {t("common.clear")}
          </button>
        )}

        <span className="ml-auto text-[11px] text-fg-4">
          {t("ministries.shownCount", {
            shown: groups.length,
            total: isMinistry ? data.totalMinistries : data.totalSectors,
          })}
        </span>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-2xl border border-line bg-raised p-8 text-center text-sm text-fg-3">
          {isMinistry
            ? t("ministries.noMinistryMatch", { query })
            : t("ministries.noSectorMatch", { query })}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {groups.map((g) => (
            <button
              key={g.name}
              onClick={() => setSelected(g)}
              className="rounded-2xl border border-line bg-raised p-5 text-left shadow-sm transition hover:-translate-y-1 hover:shadow-lg"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="rounded-xl bg-brand-subtle p-3 text-brand-hover">
                  {isMinistry ? <Building2 size={20} /> : <Layers size={20} />}
                </div>
                <span
                  className={`text-sm font-bold ${
                    g.onTrackSharePercent >= 70
                      ? "text-risk-low"
                      : g.onTrackSharePercent >= 50
                        ? "text-fg-2"
                        : "text-risk-high"
                  }`}
                >
                  {g.onTrackSharePercent}%
                </span>
              </div>

              <h3 className="mt-4 font-bold text-fg">{g.name}</h3>

              <p className="mt-1 text-xs text-fg-3">
                {t("ministries.monitoredProjects", { n: g.projectCount.toLocaleString() })}
              </p>

              <div className="mt-5 grid grid-cols-2 gap-2">
                <Metric
                  label={t("ministries.onTrack")}
                  value={g.onTrackCount.toLocaleString()}
                />
                <Metric
                  label={t("ministries.portfolioCost")}
                  value={
                    g.totalOriginalCostCrore === null
                      ? t("ministries.noCostData")
                      : formatCr(Math.round(g.totalOriginalCostCrore))
                  }
                />
              </div>

              <p className="mt-2 text-[10px] text-fg-4">{t("ministries.barNote")}</p>
              <div className="mt-1 h-2 rounded-full bg-sunken">
                <div
                  className="h-full rounded-full bg-brand"
                  style={{ width: `${g.onTrackSharePercent}%` }}
                />
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="rounded-2xl border border-brand-border bg-brand-subtle p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-bold uppercase text-brand">
                {selected.kind === "ministry"
                  ? t("ministries.selectedMinistry")
                  : t("ministries.selectedSector")}
              </p>
              <h3 className="mt-1 text-lg font-bold text-fg">{selected.name}</h3>
            </div>
            <button onClick={() => setSelected(null)} aria-label={t("ministries.close")}>
              <X size={18} />
            </button>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <Metric label={t("common.projects")} value={selected.projectCount.toLocaleString()} />
            <Metric
              label={t("ministries.onTrack")}
              value={`${selected.onTrackCount.toLocaleString()} (${selected.onTrackSharePercent}%)`}
            />
            <Metric
              label={t("ministries.needsAttention")}
              value={selected.delayedCount.toLocaleString()}
            />
            <Metric
              label={t("ministries.portfolioCost")}
              value={
                selected.totalOriginalCostCrore === null
                  ? t("ministries.noCostData")
                  : formatCr(Math.round(selected.totalOriginalCostCrore))
              }
            />
          </div>

          {selected.avgCompletionPercent !== null && (
            <p className="mt-3 text-xs text-fg-2">
              {t("ministries.meanCompletion", { pct: selected.avgCompletionPercent })}
            </p>
          )}

          {selected.childSectors.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-bold text-fg-2">{t("ministries.childSectors")}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {selected.childSectors.map((s) => (
                  <span
                    key={s}
                    className="rounded-lg bg-page px-2 py-1 text-[11px] font-semibold text-fg-2"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
