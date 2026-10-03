import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  Layers,
  Map as MapIcon,
  MapPinOff,
  Search,
  X,
} from "lucide-react";
import { fetchStateGeo, fetchStateVegetation } from "../../api";
import { StatCard } from "../../components/ui/StatCard";
import { ExportButton } from "../../components/ui/ExportButton";
import { PageHeader } from "../../components/ui/PageHeader";
import { StateMap } from "../../components/StateMap";
import { VegetationPanel } from "../../components/VegetationPanel";
import { useT } from "../../hooks/useT";

export { StatesPage };

function StatesPage({ setSearch, setActive }) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [sortBy, setSortBy] = useState("projects");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [vegetation, setVegetation] = useState(null);
  const [vegDate, setVegDate] = useState(null);
  const [vegLoading, setVegLoading] = useState(true);
  const [vegError, setVegError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchStateGeo()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || t("states.loadError"));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  // Satellite vegetation is loaded separately and is allowed to fail on its
  // own. The state directory is the primary content of this page, and it must
  // not go blank because a third-party imagery service was unreachable.
  useEffect(() => {
    let cancelled = false;
    fetchStateVegetation(vegDate)
      .then((v) => {
        if (cancelled) return;
        setVegetation(v);
        // Trust the date the server used, not the one requested. The endpoint
        // falls back to the latest acquisition when the requested date was
        // never measured, and displaying the requested date against another
        // date's numbers would be a silent substitution.
        setVegDate(v.selectedDate);
      })
      .catch((e) => {
        if (!cancelled) setVegError(e?.message || t("states.vegLoadError"));
      })
      .finally(() => {
        if (!cancelled) setVegLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [vegDate, t]);

  // The loading flag is raised in the event that changes the date rather than
  // at the top of the effect, so the effect is purely a fetch.
  const changeVegDate = (next) => {
    setVegError(null);
    setVegLoading(true);
    setVegDate(next);
  };

  const vegByState = useMemo(() => {
    const out = {};
    for (const s of vegetation?.states ?? []) out[s.state] = s;
    return out;
  }, [vegetation]);

  const rows = useMemo(() => {
    if (!data) return [];
    return data.states.map((s) => ({
      ...s,
      delayedShare: s.project_count ? (s.delayed_count / s.project_count) * 100 : 0,
      vegetation: vegByState[s.state] ?? null,
      evi_median: vegByState[s.state]?.evi_median ?? null,
    }));
  }, [data, vegByState]);

  const totalStates = rows.filter((s) => s.entity_type === "State").length;
  const totalUTs = rows.filter((s) => s.entity_type === "Union Territory").length;
  const totalProjects = data?.totalProjects ?? 0;
  const unplacedTotal = (data?.unplaced ?? []).reduce((a, b) => a + b.project_count, 0);
  const avgProgress = useMemo(
    () =>
      rows.length
        ? Math.round(rows.reduce((a, s) => a + s.avg_completion_percent, 0) / rows.length)
        : 0,
    [rows],
  );
  const delayedTotal = rows.reduce((a, s) => a + s.delayed_count, 0);

  const filtered = useMemo(() => {
    let result = rows.filter((state) => {
      const matchesQuery = state.state.toLowerCase().includes(query.toLowerCase().trim());
      if (!matchesQuery) return false;
      if (filterType === "states") return state.entity_type === "State";
      if (filterType === "uts") return state.entity_type === "Union Territory";
      if (filterType === "delayed") return state.delayedShare >= 50;
      return true;
    });

    return result.sort((a, b) => {
      if (sortBy === "projects") return b.project_count - a.project_count;
      if (sortBy === "delayed") return b.delayedShare - a.delayedShare;
      if (sortBy === "progress") return b.avg_completion_percent - a.avg_completion_percent;
      if (sortBy === "name") return a.state.localeCompare(b.state);
      return 0;
    });
  }, [rows, query, filterType, sortBy]);

  const handleExploreState = (stateName) => {
    if (setSearch) setSearch(stateName);
    if (setActive) setActive("projects");
  };

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader
          icon={MapIcon}
          title={t("states.title")}
          subtitle={t("states.subtitle")}
        />
        <div className="rounded-2xl border border-line bg-raised p-10 text-center">
          <AlertTriangle className="mx-auto text-risk-high" size={30} />
          <h3 className="mt-3 text-sm font-bold text-fg">{t("states.unavailable")}</h3>
          <p className="mt-1 text-xs text-fg-3">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6">
        <PageHeader
          icon={MapIcon}
          title={t("states.title")}
          subtitle={t("states.subtitle")}
        />
        <div className="h-[420px] animate-pulse rounded-2xl border border-line bg-raised" />
      </div>
    );
  }

  const distinctPoints = data.states.length;
  const coverageNote = t("states.coverageNote", {
    attributed: data.stateAttributedProjects.toLocaleString(),
    total: totalProjects.toLocaleString(),
    share: data.stateAttributedSharePercent,
    points: distinctPoints.toLocaleString(),
  });

  // `bucket` and `entity_type` are English values straight from the API. They
  // are only ever displayed, never compared, so mapping them for display is
  // safe -- the filter above keeps comparing the raw API string.
  const bucketLabel = (name) => {
    const key = {
      "Multi-State": "states.bucketMultiState",
      "PAN India": "states.bucketPanIndia",
      Offshore: "states.bucketOffshore",
      Unspecified: "states.bucketUnspecified",
    }[name];
    return key ? t(key) : name;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        icon={MapIcon}
        title={t("states.title")}
        subtitle={t("states.pageSubtitle", {
          coverage: coverageNote,
          unplaced: unplacedTotal.toLocaleString(),
        })}
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={MapIcon}
          title={t("states.covered")}
          value={`${totalStates + totalUTs}`}
          subtitle={t("states.coveredSub", { states: totalStates, uts: totalUTs })}
          hue="cyan"
        />
        <StatCard
          icon={Building2}
          title={t("states.monitoredProjects")}
          value={totalProjects.toLocaleString()}
          subtitle={t("states.avgProgressSub", { pct: avgProgress })}
          hue="fuchsia"
        />
        <StatCard
          icon={AlertTriangle}
          title={t("states.delayedProjects")}
          value={delayedTotal.toLocaleString()}
          subtitle={t("states.ofPortfolio", {
            pct: Math.round((delayedTotal / (totalProjects || 1)) * 100),
          })}
          hue="cyan"
        />
        <StatCard
          icon={MapPinOff}
          title={t("states.noSingleState")}
          value={unplacedTotal.toLocaleString()}
          subtitle={t("states.multiStateSub")}
          hue="cyan"
        />
      </div>

      <StateMap
        states={rows}
        unplaced={data.unplaced}
        hasVegetation={Boolean(vegetation?.states?.length)}
        eviDate={vegetation?.selectedDate ?? null}
        onSelect={(name) => {
          setSelected(name);
          setQuery(name);
        }}
      />

      <VegetationPanel
        vegetation={vegetation}
        selectedDate={vegetation?.selectedDate ?? vegDate}
        onDateChange={changeVegDate}
        loading={vegLoading}
        error={vegError}
      />

      {selected && (
        <div className="flex items-center justify-between rounded-2xl border border-brand-border bg-brand-subtle px-4 py-3">
          <p className="text-xs text-brand-hover">
            {t("states.selectedBanner", { state: selected })}
          </p>
          <button
            onClick={() => {
              setSelected(null);
              setQuery("");
            }}
            className="text-brand-hover hover:underline"
          >
            <X size={15} />
          </button>
        </div>
      )}

      <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-1 items-center gap-2 rounded-xl border border-line bg-page px-3 py-2 transition focus-within:border-brand focus-within:ring-2 focus-within:ring-brand-subtle">
            <Search size={17} className="shrink-0 text-fg-4" />
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelected(null);
              }}
              placeholder={t("states.searchPlaceholder")}
              className="w-full bg-transparent text-sm text-fg outline-none placeholder:text-fg-4"
            />
            {query && (
              <button
                onClick={() => {
                  setQuery("");
                  setSelected(null);
                }}
                className="text-fg-4 hover:text-fg-2"
                title={t("states.clearQuery")}
                aria-label={t("states.clearQuery")}
              >
                <X size={15} />
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-xl border border-line bg-page p-1 text-xs font-semibold">
              <button
                onClick={() => setFilterType("all")}
                className={`rounded-lg px-3 py-1.5 transition ${
                  filterType === "all" ? "bg-raised text-brand-hover shadow-sm" : "text-fg-2 hover:text-fg"
                }`}
              >
                {t("states.filterAll", { n: rows.length })}
              </button>
              <button
                onClick={() => setFilterType("states")}
                className={`rounded-lg px-3 py-1.5 transition ${
                  filterType === "states" ? "bg-raised text-brand-hover shadow-sm" : "text-fg-2 hover:text-fg"
                }`}
              >
                {t("states.filterStates", { n: totalStates })}
              </button>
              <button
                onClick={() => setFilterType("uts")}
                className={`rounded-lg px-3 py-1.5 transition ${
                  filterType === "uts" ? "bg-raised text-brand-hover shadow-sm" : "text-fg-2 hover:text-fg"
                }`}
              >
                {t("states.filterUts", { n: totalUTs })}
              </button>
              <button
                onClick={() => setFilterType("delayed")}
                className={`rounded-lg px-3 py-1.5 transition ${
                  filterType === "delayed" ? "bg-risk-high text-white shadow-sm" : "text-fg-2 hover:text-fg"
                }`}
              >
                {t("states.filterDelayed")}
              </button>
            </div>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="rounded-xl border border-line bg-raised px-3 py-2 text-xs font-semibold text-fg-2 outline-none"
            >
              <option value="projects">{t("states.sortProjects")}</option>
              <option value="delayed">{t("states.sortDelayed")}</option>
              <option value="progress">{t("states.sortProgress")}</option>
              <option value="name">{t("states.sortName")}</option>
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-2 border-b border-line pb-3 text-xs text-fg-3 md:flex-row md:items-center md:justify-between">
          <span>{t("states.showing", { shown: filtered.length, total: rows.length })}</span>

          <div className="flex flex-wrap items-center gap-2">
            <ExportButton
              label={t("common.exportCsv")}
              filename="mospi-state-wise-projects.csv"
              rows={filtered.map((s) => ({
                [t("states.csvState")]: s.state,
                [t("states.csvType")]:
                  s.entity_type === "Union Territory" ? t("states.entityUt") : t("states.entityState"),
                [t("states.csvMonitored")]: s.project_count,
                [t("states.csvOnTrack")]: s.on_track_count,
                [t("states.csvDelayed")]: s.delayed_count,
                [t("states.csvDelayedPct")]: Math.round(s.delayedShare),
                [t("states.csvAvgProgress")]: s.avg_completion_percent,
              }))}
            />

            {(query || filterType !== "all" || sortBy !== "projects") && (
              <button
                onClick={() => {
                  setQuery("");
                  setFilterType("all");
                  setSortBy("projects");
                  setSelected(null);
                }}
                className="font-semibold text-brand hover:underline"
              >
                {t("states.resetView")}
              </button>
            )}
          </div>
        </div>

        {filtered.length > 0 ? (
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map((state) => (
              <div
                key={state.state}
                className="group flex flex-col justify-between rounded-2xl border border-line bg-raised p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-brand-border hover:shadow-md"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span
                        className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                          state.entity_type === "Union Territory"
                            ? "bg-brand-subtle text-chart-3"
                            : "bg-brand-subtle text-brand-hover"
                        }`}
                      >
                        {state.entity_type === "Union Territory"
                          ? t("states.entityUt")
                          : t("states.entityState")}
                      </span>
                      <h3 className="mt-1 font-bold text-fg line-clamp-1 group-hover:text-brand transition">
                        {state.state}
                      </h3>
                    </div>
                    <span
                      className={`inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-bold ${
                        state.delayedShare >= 50
                          ? "bg-risk-high text-white"
                          : state.delayedShare >= 30
                            ? "bg-risk-medium-subtle text-risk-medium"
                            : "bg-risk-low-subtle text-risk-low"
                      }`}
                      title={t("states.delayedTitle")}
                    >
                      {t("states.delayedPct", { pct: Math.round(state.delayedShare) })}
                    </span>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-xs text-fg-2">
                    <span>{t("states.monitoredCount", { n: state.project_count })}</span>
                    <span className="text-[11px] font-semibold text-fg-3">
                      {t("states.onTrack", { n: state.on_track_count })}
                    </span>
                  </div>

                  <div className="mt-3">
                    <div className="mb-1 flex justify-between text-[10px] text-fg-3">
                      <span>{t("states.averageProgress")}</span>
                      <span className="font-semibold">{state.avg_completion_percent}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-sunken">
                      <div
                        className={`h-full rounded-full transition-all ${
                          state.avg_completion_percent >= 70
                            ? "bg-risk-low"
                            : state.avg_completion_percent >= 50
                              ? "bg-brand"
                              : "bg-risk-high"
                        }`}
                        style={{ width: `${state.avg_completion_percent}%` }}
                      />
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleExploreState(state.state)}
                  className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-xl bg-page py-2 text-xs font-bold text-fg-2 transition hover:bg-brand-subtle hover:text-brand-hover"
                >
                  {t("states.explore")} <ArrowUpRight size={13} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-16 text-center">
            <MapIcon className="mx-auto text-fg-4" size={36} />
            <h3 className="mt-3 text-base font-bold text-fg">
              {t("states.noMatch", { query })}
            </h3>
            <p className="mt-1 text-xs text-fg-3">{t("states.noMatchHint")}</p>
            <button
              onClick={() => {
                setQuery("");
                setFilterType("all");
                setSelected(null);
              }}
              className="mt-4 rounded-xl bg-brand px-4 py-2 text-xs font-bold text-white transition hover:bg-brand-hover"
            >
              {t("states.showAll")}
            </button>
          </div>
        )}
      </div>

      {unplacedTotal > 0 && (
        <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-fg-3" />
            <h3 className="text-sm font-bold text-fg">{t("states.unplacedTitle")}</h3>
          </div>
          <p className="mt-1 text-xs text-fg-3">{t("states.unplacedBody")}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {data.unplaced.map((b) => (
              <div key={b.bucket} className="rounded-xl border border-line bg-page p-3">
                <div className="text-[10px] font-bold uppercase tracking-wide text-fg-3">
                  {bucketLabel(b.bucket)}
                </div>
                <div className="mt-1 text-lg font-bold text-fg">{b.project_count}</div>
                <div className="text-[11px] text-fg-3">
                  {t("states.pctOfPortfolio", {
                    pct: Math.round((b.project_count / (totalProjects || 1)) * 100),
                  })}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-start gap-2 rounded-xl bg-sunken p-3 text-[11px] text-fg-3">
            <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-risk-low" />
            <span>{t("states.unplacedNote")}</span>
          </div>
        </div>
      )}
    </div>
  );
}
