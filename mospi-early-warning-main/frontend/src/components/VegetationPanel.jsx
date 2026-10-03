import { useMemo, useState } from "react";

import { useT } from "../hooks/useT";

/**
 * Satellite vegetation panel.
 *
 * Everything here is measured per state from MODIS Terra, and the panel is
 * built so that it cannot be read as per-project monitoring. There is no
 * project count, no rupee figure and no project identifier anywhere in it,
 * and the limitations are stated on the surface rather than buried in a
 * tooltip.
 *
 * The date selector shows real acquisition dates read from the source service,
 * not a synthetic time axis, and it only offers dates that were actually
 * measured.
 */
export function VegetationPanel({ vegetation, selectedDate, onDateChange, loading, error }) {
  const t = useT();
  const [showLimits, setShowLimits] = useState(false);

  const ranked = useMemo(
    () => [...(vegetation?.states ?? [])].sort(
      (a, b) => (b.evi_median ?? -9) - (a.evi_median ?? -9),
    ),
    [vegetation],
  );

  const movers = useMemo(() => {
    const t = (vegetation?.trends ?? []).filter((x) => x.change_per_month != null);
    return {
      rising: [...t].sort((a, b) => b.change_per_month - a.change_per_month).slice(0, 5),
      falling: [...t].sort((a, b) => a.change_per_month - b.change_per_month).slice(0, 5),
    };
  }, [vegetation]);

  if (error) {
    return (
      <section className="rounded-2xl border border-line bg-raised p-4 shadow-sm">
        <h3 className="text-sm font-bold text-fg">{t("veg.title")}</h3>
        <p className="mt-2 text-[11px] text-fg-3">{t("veg.loadError")}</p>
      </section>
    );
  }

  if (loading || !vegetation) {
    return (
      <section className="rounded-2xl border border-line bg-raised p-4 shadow-sm">
        <h3 className="text-sm font-bold text-fg">{t("veg.title")}</h3>
        <p className="mt-2 text-[11px] text-fg-3">{t("veg.loading")}</p>
      </section>
    );
  }

  if (!(vegetation.dates?.length)) {
    return (
      <section className="rounded-2xl border border-line bg-raised p-4 shadow-sm">
        <h3 className="text-sm font-bold text-fg">{t("veg.title")}</h3>
        <p className="mt-2 text-[11px] text-fg-3">
          {t("veg.noAcquisitions", {
            script: "backend/scripts/compute_vegetation.py",
          })}
        </p>
      </section>
    );
  }

  const outlierCount = vegetation.dates.find((d) => d.acquisition_date === selectedDate)
    ?.low_outlier_count ?? 0;

  return (
    <section className="rounded-2xl border border-line bg-raised shadow-sm">
      <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-sm font-bold text-fg">{t("veg.title")}</h3>
          <p className="mt-0.5 text-[11px] text-fg-3">
            {t("veg.summary", {
              n: vegetation.states.length,
              date: selectedDate,
            })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label
            className="text-[11px] font-semibold text-fg-2"
            htmlFor="evi-acquisition"
          >
            {t("veg.acquisition")}
          </label>
          <select
            id="evi-acquisition"
            value={selectedDate ?? ""}
            onChange={(e) => onDateChange(e.target.value)}
            className="rounded-lg border border-line bg-page px-2 py-1.5 text-[11px] font-semibold text-fg"
          >
            {vegetation.dates.map((d) => (
              <option key={d.acquisition_date} value={d.acquisition_date}>
                {d.acquisition_date}
                {d.is_latest ? t("veg.latest") : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {outlierCount > 0 && (
        <div className="border-b border-line bg-amber-50/60 px-4 py-2.5">
          <p className="text-[11px] font-semibold text-amber-900">
            {t("veg.outlierWarning", {
              n: outlierCount,
              unit: t(
                outlierCount === 1 ? "veg.outlierUnitOne" : "veg.outlierUnitMany",
              ),
            })}
          </p>
          <p className="mt-0.5 text-[11px] text-amber-800">
            {t("veg.outlierExplain")}
          </p>
        </div>
      )}

      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <div>
          <h4 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-fg-3">
            {t("veg.highestOn", { date: selectedDate })}
          </h4>
          <ul className="space-y-1">
            {ranked.slice(0, 6).map((s) => (
              <li key={s.state} className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className="flex items-center gap-1.5 text-fg-2">
                  {s.low_outlier && (
                    <span
                      className="rounded bg-amber-100 px-1 text-[9px] font-bold text-amber-800"
                      title={t("veg.lowOutlierTitle")}
                    >
                      ?
                    </span>
                  )}
                  {s.state}
                </span>
                <span className="shrink-0 font-mono text-fg">
                  {s.evi_median?.toFixed(3) ?? "—"}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <h4 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-fg-3">
              {t("veg.greening")}
            </h4>
            <ul className="space-y-1">
              {movers.rising.map((t) => (
                <li key={t.state} className="flex items-baseline justify-between gap-2 text-[11px]">
                  <span className="truncate text-fg-2">{t.state}</span>
                  <span className="shrink-0 font-mono text-emerald-700">
                    {t.change_per_month > 0 ? "+" : ""}
                    {t.change_per_month.toFixed(3)}
                  </span>
                </li>
              ))}
              {!movers.rising.length && (
                <li className="text-[11px] text-fg-3">{t("veg.needTwo")}</li>
              )}
            </ul>
          </div>
          <div>
            <h4 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-fg-3">
              {t("veg.declining")}
            </h4>
            <ul className="space-y-1">
              {movers.falling.map((t) => (
                <li key={t.state} className="flex items-baseline justify-between gap-2 text-[11px]">
                  <span className="truncate text-fg-2">{t.state}</span>
                  <span className="shrink-0 font-mono text-amber-700">
                    {t.change_per_month > 0 ? "+" : ""}
                    {t.change_per_month.toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="border-t border-line px-4 py-2.5">
        <button
          onClick={() => setShowLimits((v) => !v)}
          className="text-[11px] font-semibold text-brand-hover"
        >
          {showLimits ? t("veg.hide") : t("veg.showLimits")}
        </button>
        {showLimits && (
          <ul className="mt-2 space-y-1.5">
            {vegetation.limitations.map((l, i) => (
              <li key={i} className="text-[11px] leading-relaxed text-fg-3">
                • {l}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/** Small inline readout used beside the state table. */
export function VegetationCell({ veg }) {
  const t = useT();
  if (!veg || veg.evi_median == null) {
    return <span className="text-fg-3">{t("veg.notMeasured")}</span>;
  }
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className="font-mono">{veg.evi_median.toFixed(3)}</span>
      {veg.low_outlier && (
        <span
          className="rounded bg-amber-100 px-1 text-[9px] font-bold text-amber-800"
          title={veg.outlier_note || t("veg.lowOutlierShort")}
        >
          ?
        </span>
      )}
      <span className="text-[9px] text-fg-3">
        {t("veg.pctClear", {
          pct: Math.round((veg.valid_pixel_fraction ?? 0) * 100),
        })}
      </span>
    </span>
  );
}
