import { CountUp } from "./CountUp";

export { StatCard, STAT_HUE };

/**
 * Hue recipes for a stat card.
 *
 * `StatCard` originally took an `accent` prop holding a raw Tailwind class
 * string (e.g. "bg-blue-50 text-blue-600") painted on a flat square. That is
 * why the icon tiles read as inert: a pale square with a coloured glyph
 * carries no depth and no identity.
 *
 * `hue` names one of these recipes instead. Each supplies a gradient tile
 * plus a soft corner wash on the card body, so a wall of stats gains colour
 * and depth without any of the cards shouting. Class names are literal so
 * Tailwind's scanner can see them - `bg-${hue}` compiles to nothing.
 */
const STAT_HUE = {
  violet: {
  tile: "bg-gradient-to-br from-cat-1 to-cat-1/70",
  on: "text-brand-fg",
  wash: "before:bg-gradient-to-br before:from-cat-1/8 before:via-transparent before:to-transparent",
  edge: "hover:border-cat-1/45",
  },
  fuchsia: {
  tile: "bg-gradient-to-br from-cat-2 to-cat-2/70",
  on: "text-brand-fg",
  wash: "before:bg-gradient-to-br before:from-cat-2/8 before:via-transparent before:to-transparent",
  edge: "hover:border-cat-2/45",
  },
  cyan: {
  tile: "bg-gradient-to-br from-cat-3 to-cat-3/70",
  on: "text-brand-fg",
  wash: "before:bg-gradient-to-br before:from-cat-3/8 before:via-transparent before:to-transparent",
  edge: "hover:border-cat-3/45",
  },
  emerald: {
  tile: "bg-gradient-to-br from-cat-4 to-cat-4/70",
  on: "text-brand-fg",
  wash: "before:bg-gradient-to-br before:from-cat-4/8 before:via-transparent before:to-transparent",
  edge: "hover:border-cat-4/45",
  },
  amber: {
  tile: "bg-gradient-to-br from-cat-5 to-cat-5/70",
  on: "text-brand-fg",
  wash: "before:bg-gradient-to-br before:from-cat-5/8 before:via-transparent before:to-transparent",
  edge: "hover:border-cat-5/45",
  },
  rose: {
  tile: "bg-gradient-to-br from-cat-6 to-cat-6/70",
  on: "text-brand-fg",
  wash: "before:bg-gradient-to-br before:from-cat-6/8 before:via-transparent before:to-transparent",
  edge: "hover:border-cat-6/45",
  },
  };

/**
 * `hue` defaults to null, NOT to a colour, and that is deliberate.
 *
 * Several call sites label a card with a risk tier ("Critical", "Cost
 * Risk", "High Cost Risk"). Those cards must keep the risk ramp: red on a
 * card called Critical is data encoding, and swapping it for a decorative
 * violet would make the dashboard prettier and less truthful. A default hue
 * would silently repaint them, so the gradient is opt-in and risk-labelled
 * cards are left on the reserved scale.
 */
function StatCard({ icon: Icon, title, value, subtitle, accent, hue = null }) {
  const palette = STAT_HUE[hue] || STAT_HUE.indigo;

  // `accent` stays supported for callers that have not migrated to `hue`;
  // when both are present the hue recipe wins because it carries the
  // gradient and the corner wash.
  const tile = palette ? palette.tile : accent;
  const tileText = palette ? palette.on : "";

  return (
  <div
  className={`group relative overflow-hidden rounded-2xl border border-line bg-raised p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-lg ${
  palette ? palette.edge : ""
  }`}
  >
  {/* Corner wash: a single low-alpha hue bleed from the top-left, clipped
      by the card radius. Gives the card a lit surface instead of a flat
      white rectangle. */}
  {palette && (
  <span
  className={`pointer-events-none absolute inset-0 ${palette.wash}`}
  aria-hidden="true"
  />
  )}

  <div className="relative flex items-start justify-between">
  <div className="min-w-0">
  <p className="text-xs font-semibold uppercase tracking-wider text-fg-3">
  {title}
  </p>

  <h2 className="mt-2 text-[26px] font-bold leading-none tracking-tight text-fg">
  <CountUp value={value} />
  </h2>

  {subtitle && <p className="mt-1.5 text-xs text-fg-3">{subtitle}</p>}
  </div>

  <div
  className={`shrink-0 rounded-xl p-3 shadow-sm transition-transform duration-300 group-hover:scale-105 ${
  tile
  } ${tileText}`}
  >
  {Icon && <Icon size={21} />}
  </div>
  </div>
  </div>
  );
}
