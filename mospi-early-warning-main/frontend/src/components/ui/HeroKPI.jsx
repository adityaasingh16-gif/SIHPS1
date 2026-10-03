import { CountUp } from "./CountUp";

export { HeroKPI, CompactStat };

/**
 * Dashboard hero: one dominant metric plus compact supporting tiles.
 *
 * The previous layout was four identical cards in a row, which is the single
 * most recognisable "unconfigured dashboard" shape. Asymmetry reads as
 * deliberate. It also puts the number people actually open the app for -
 * how much of the budget has been spent - at a size that matches its
 * importance, instead of burying it as a subtitle.
 */

/**
 * Dominant metric panel.
 *
 * `progress` renders a meter when the metric is a fraction of a known total
 * (expenditure against revised cost). The meter is paired with a text
 * equivalent for screen readers, because a bare gradient bar conveys nothing
 * to a screen reader or to someone who cannot distinguish the fill from the
 * track.
 */
function HeroKPI({
  label,
  value,
  unit,
  caption,
  progress,
  progressLabel,
  meta = [],
  icon: Icon,
}) {
  const pct =
    typeof progress === "number" && Number.isFinite(progress)
      ? Math.max(0, Math.min(100, progress))
      : null;

  return (
    <section
      className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand via-brand to-brand-active p-6 text-white shadow-pop md:p-7"
      aria-label={label}
    >
      {/* Soft radial highlight so the panel has a light source instead of
          reading as a flat rectangle of colour. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-white/10 blur-3xl"
      />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-28 -left-10 h-56 w-56 rounded-full bg-cat-2/25 blur-3xl"
      />

      <div className="relative">
        <div className="flex items-center gap-2">
          {Icon && <Icon size={15} className="opacity-90" aria-hidden="true" />}
          <p className="text-[11px] font-bold uppercase tracking-widest text-white/75">
            {label}
          </p>
        </div>

        <p className="mt-3 flex items-baseline gap-1.5">
          <span className="text-[44px] font-bold leading-none tracking-tight tabular-nums md:text-[52px]">
            <CountUp value={value} />
          </span>
          {unit && (
            <span className="text-xl font-semibold text-white/80">{unit}</span>
          )}
        </p>

        {caption && (
          <p className="mt-2 text-xs leading-5 text-white/75">{caption}</p>
        )}

        {pct !== null && (
          <div className="mt-5">
            <div
              role="progressbar"
              aria-valuenow={Math.round(pct)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={progressLabel || label}
              className="h-2 w-full overflow-hidden rounded-full bg-white/20"
            >
              <div
                className="h-full rounded-full bg-white transition-[width] duration-700 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
            {progressLabel && (
              <p className="mt-2 text-[11px] text-white/70">{progressLabel}</p>
            )}
          </div>
        )}

        {meta.length > 0 && (
          <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-white/15 pt-4 sm:grid-cols-3">
            {meta.map((m) => (
              <div key={m.label} className="min-w-0">
                <dt className="truncate text-[10px] font-semibold uppercase tracking-wider text-white/60">
                  {m.label}
                </dt>
                <dd className="mt-0.5 truncate text-sm font-semibold tabular-nums">
                  {m.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  );
}

/**
 * Compact supporting tile - the same information as a StatCard but sized to
 * sit beside a hero without competing with it.
 */
function CompactStat({ label, value, subtitle, icon: Icon, hue = "cyan", trend, tone = "subtle" }) {
  const TONES = {
    violet: "bg-cat-1-subtle text-cat-1-subtle-fg",
    fuchsia: "bg-cat-2-subtle text-cat-2-subtle-fg",
    cyan: "bg-cat-3-subtle text-cat-3-subtle-fg",
    emerald: "bg-cat-4-subtle text-cat-4-subtle-fg",
    amber: "bg-cat-5-subtle text-cat-5-subtle-fg",
    rose: "bg-cat-6-subtle text-cat-6-subtle-fg",
  };
  const SOLID = {
    violet: "bg-cat-1 text-white",
    fuchsia: "bg-cat-2 text-white",
    cyan: "bg-cat-3 text-white",
    emerald: "bg-cat-4 text-white",
    amber: "bg-cat-5 text-white",
    rose: "bg-cat-6 text-white",
  };

  return (
    <div className="group flex items-start gap-3.5 rounded-2xl border border-line bg-raised p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-card">
      {Icon && (
        <div
          className={`shrink-0 rounded-xl p-2.5 shadow-sm transition-transform duration-300 group-hover:scale-105 ${
            tone === "solid"
              ? SOLID[hue] || SOLID.cyan
              : TONES[hue] || TONES.cyan
          }`}
          aria-hidden="true"
        >
          <Icon size={18} />
        </div>
      )}

      <div className="min-w-0 flex-1">
        <p className="truncate text-[10px] font-bold uppercase tracking-wider text-fg-3">
          {label}
        </p>

        <p className="mt-1 flex items-baseline gap-1.5">
          <span className="truncate text-xl font-bold leading-none tracking-tight tabular-nums text-fg">
            <CountUp value={value} />
          </span>
          {trend && (
            <span
              className={`shrink-0 text-[11px] font-semibold tabular-nums ${
                trend.direction === "up" ? "text-risk-high" : "text-risk-low"
              }`}
            >
              {trend.label}
            </span>
          )}
        </p>

        {subtitle && (
          <p className="mt-1 truncate text-[11px] text-fg-3">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
