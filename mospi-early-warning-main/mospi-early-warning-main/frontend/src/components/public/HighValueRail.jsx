/**
 * "High Value Projects" card rail — the signature visual of the MoSPI Dhrishti
 * public homepage, ported to React and wired to live data.
 *
 * The live portal renders these as a Slick carousel with `centerMode`, so the
 * middle card is full-width and its neighbours are clipped at the edges. A CSS
 * scroll-snap rail reproduces that at any viewport width and, unlike a JS
 * carousel, keeps the cards in the accessibility tree and keyboard-reachable.
 *
 * Each card carries the four figures the portal shows: original cost, physical
 * progress, latest revised cost, and latest revised completion date.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, IndianRupee } from "lucide-react";

const SECTOR_HUES = [
  "bg-[#4e1a79]",
  "bg-[#ef8222]",
  "bg-[#3297cc]",
  "bg-[#e7317d]",
  "bg-[#ab8fdf]",
  "bg-[#f6be0c]",
  "bg-[#7cbb43]",
  "bg-[#73a2ad]",
  "bg-[#e54126]",
  "bg-[#872575]",
  "bg-[#5c3a1c]",
];

const TIER_TEXT = {
  Critical: "text-risk-critical",
  High: "text-risk-high",
  Medium: "text-risk-medium",
  Low: "text-risk-low",
};

function hueForSector(sector) {
  let hash = 0;
  const key = String(sector || "");
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash + key.charCodeAt(i)) % SECTOR_HUES.length;
  }
  return SECTOR_HUES[hash];
}

function inr(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "—";
  if (n >= 1e5) return `${(n / 1e5).toFixed(2)} lakh cr`;
  return `${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })} cr`;
}

function pct(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(0)}%` : "—";
}

function asDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function HighValueRail({ projects, loading, t }) {
  const railRef = useRef(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  const syncEdges = useCallback(() => {
    const el = railRef.current;
    if (!el) return;
    setAtStart(el.scrollLeft <= 4);
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    syncEdges();
    const el = railRef.current;
    if (!el) return undefined;
    el.addEventListener("scroll", syncEdges, { passive: true });
    window.addEventListener("resize", syncEdges);
    return () => {
      el.removeEventListener("scroll", syncEdges);
      window.removeEventListener("resize", syncEdges);
    };
  }, [syncEdges, projects]);

  const nudge = (dir) => {
    const el = railRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * Math.max(280, el.clientWidth * 0.8), behavior: "smooth" });
  };

  return (
    <div className="relative">
      {/* `contain: paint` is load-bearing, not decoration. Without it the rail's
          scrollable overflow propagates to the document, which makes the whole
          page as wide as all 14 cards laid out end to end (~4.4k px) and
          horizontally scrollable. The arrows are siblings of this element, not
          descendants, so paint containment leaves them visible. */}
      <div
        ref={railRef}
        className="flex snap-x snap-mandatory gap-5 overflow-x-auto pb-4 [contain:paint] [scrollbar-width:thin]"
        role="region"
        aria-label={t("public.highValue")}
        tabIndex={0}
      >
        {loading && projects.length === 0
          ? Array.from({ length: 4 }).map((_, i) => (
              <div
                key={`skeleton-${i}`}
                className="w-[300px] shrink-0 snap-center rounded-[20px] border border-line-strong bg-raised p-4"
              >
                <div className="skeleton h-4 w-2/3" />
                <div className="skeleton mt-3 h-3 w-1/2" />
                <div className="skeleton mt-6 h-16 w-full" />
              </div>
            ))
          : projects.map((p) => (
              <article
                key={p.project_id}
                className="group w-[300px] shrink-0 snap-center rounded-[20px] border border-line-strong bg-raised p-4 shadow-card transition-transform duration-300 hover:scale-[1.02]"
              >
                <header className="flex items-center gap-3 border-b border-line pb-3">
                  <span
                    aria-hidden="true"
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${hueForSector(p.sector)}`}
                  >
                    <IndianRupee size={20} className="text-white" />
                  </span>
                  <div className="min-w-0">
                    <h3 className="truncate text-[10px] font-bold uppercase tracking-wider text-[#060e37] dark:text-white">
                      {p.sector}
                    </h3>
                    <p className="truncate text-[10px] font-semibold text-fg-3">
                      {p.implementing_agency && p.implementing_agency !== "nan"
                        ? p.implementing_agency
                        : p.ministry}
                    </p>
                  </div>
                </header>
                {/* `/projects` carries no project-name field, so the heading is
                    the sanctioned ID and the published summary is the prose
                    line. `title` gives keyboard and touch users the same
                    affordance the CSS line-clamp hides from them. */}
                <h3
                  title={p.public_summary || undefined}
                  className="mt-3 text-[12px] font-bold leading-snug text-fg"
                >
                  {t("public.project")} {p.project_id}
                </h3>
                {p.public_summary && (
                  <p className="mt-1 line-clamp-2 min-h-[2.2rem] text-[11px] leading-snug text-fg-3">
                    {p.public_summary}
                  </p>
                )}

                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
                  <Figure label={t("public.originalCost")} value={inr(p.original_cost_crore)} />
                  <Figure
                    label={t("public.physicalProgress")}
                    value={pct(p.completion_percent)}
                    accent
                  />
                  <Figure
                    label={t("public.revisedCost")}
                    value={inr(p.latest_revised_cost_crore)}
                  />
                  <Figure
                    label={t("public.revisedDate")}
                    value={asDate(p.planned_completion_date)}
                    small
                  />
                </dl>

                <footer className="mt-4 flex items-center justify-between border-t border-line pt-3">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-fg-3">
                    {t("public.projectId")} {p.project_id}
                  </span>
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider ${
                      TIER_TEXT[p.risk_tier] || TIER_TEXT.Low
                    }`}
                  >
                    {p.risk_tier} {t("public.riskTier")}
                  </span>
                </footer>
              </article>
            ))}
      </div>

      {!loading && projects.length > 0 && (
        <>
          <RailButton
            side="left"
            disabled={atStart}
            onClick={() => nudge(-1)}
            label={t("public.scrollHighValueLeft")}
          />
          <RailButton
            side="right"
            disabled={atEnd}
            onClick={() => nudge(1)}
            label={t("public.scrollHighValueRight")}
          />
        </>
      )}
    </div>
  );
}

function Figure({ label, value, accent = false, small = false }) {
  return (
    <div>
      <dt className="text-[9px] font-bold uppercase leading-tight tracking-wider text-fg-3">
        {label}
      </dt>
      <dd
        className={`mt-0.5 font-bold tabular-nums text-[#060e37] dark:text-white ${
          small ? "text-[13px]" : "text-[17px]"
        }`}
      >
        {value}
        {accent && value !== "—" && (
          <span className="sr-only"> {label.toLowerCase()}</span>
        )}
      </dd>
    </div>
  );
}

function RailButton({ side, disabled, onClick, label }) {
  const Icon = side === "left" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={`absolute top-1/2 z-10 hidden h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-line-strong bg-raised text-fg-2 shadow-pop transition-opacity md:flex ${
        side === "left" ? "-left-4" : "-right-4"
      } ${disabled ? "pointer-events-none opacity-0" : "hover:bg-hover"}`}
    >
      <Icon size={18} />
    </button>
  );
}
