export { CostEscalationChart };

import { useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Line,
} from "recharts";

import { ChartTooltip } from "./ChartTooltip";
import { useT } from "../../hooks/useT";

/**
 * Sanctioned -> revised cost escalation, one row per project.
 *
 * This is the central story in project monitoring and the app had no visual
 * for it: original and revised cost were only ever summed into two headline
 * totals, which hides which projects escalated and by how much. A dumbbell
 * (a connector between the original and revised point) makes the size of each
 * individual overrun legible at a glance.
 *
 * The chart plots the top N projects by absolute escalation, because a
 * thousand rows of hairlines is noise. The remainder is reported as a count
 * so the reader knows the chart is a sample and not the whole set.
 */

/** Rank projects by how far revised cost has drifted from the original. */
function pickEscalated(projects, t) {
  return projects
    .map((p) => {
      const original = Number(p.originalCost) || 0;
      const revised = Number(p.revisedCost) || 0;
      return {
        id: p.id ?? p.project_id ?? p.name,
        name: p.name || p.project_name || t("costChart.unnamed"),
        original,
        revised,
        delta: revised - original,
        pct: original > 0 ? ((revised - original) / original) * 100 : 0,
      };
    })
    // Only meaningful pairs: a project with no revised figure yet cannot be
    // plotted, and drawing it at 0 would read as a 100% cut.
    .filter((d) => d.original > 0 && d.revised > 0)
    .sort((a, b) => b.delta - a.delta);
}

function CostEscalationChart({ projects = [], limit = 12, height = 340 }) {
  const t = useT();
  const { rows, totalEligible } = useMemo(() => {
    const ranked = pickEscalated(projects, t);
    return { rows: ranked.slice(0, limit), totalEligible: ranked.length };
  }, [projects, limit, t]);

  if (rows.length === 0) {
    return (
      <div className="flex h-[340px] items-center justify-center rounded-xl border border-dashed border-line-strong text-xs text-fg-3">
        {t("costChart.empty")}
      </div>
    );
  }

  const axis = (v) => {
    // Axis ticks are read at a glance, so keep them to whole units.
    const n = Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 100 ? 0 : 2;
    return v.toLocaleString("en-IN", {
      minimumFractionDigits: n,
      maximumFractionDigits: n,
    });
  };

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={rows}
          layout="vertical"
          margin={{ top: 8, right: 92, bottom: 8, left: 8 }}
        >
          <CartesianGrid
            stroke="var(--border-subtle)"
            strokeDasharray="3 3"
            horizontal={false}
          />

          <XAxis
            type="number"
            tickFormatter={axis}
            tick={{ fill: "var(--fg-subtle)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={58}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={132}
            tick={{ fill: "var(--fg-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) =>
              v.length > 19 ? `${v.slice(0, 18)}…` : v
            }
          />

          <Tooltip
            content={<ChartTooltip />}
            cursor={{ stroke: "var(--border-strong)", strokeWidth: 1 }}
          />

          {/* Sanctioned, muted: the baseline you are comparing against. */}
          <Line
            dataKey="original"
            stroke="var(--chart-3)"
            strokeWidth={2}
            dot={{ r: 3.5, fill: "var(--chart-3)", strokeWidth: 0 }}
            activeDot={{ r: 5.5 }}
            isAnimationActive={false}
            name={t("costChart.original")}
          />

          {/* Latest revised, the accent: where the money actually landed. */}
          <Line
            dataKey="revised"
            stroke="var(--brand)"
            strokeWidth={2.5}
            strokeDasharray="5 3"
            dot={{ r: 4, fill: "var(--brand)", strokeWidth: 0 }}
            activeDot={{ r: 6 }}
            isAnimationActive={false}
            name={t("costChart.revised")}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-fg-3">
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: "var(--chart-3)" }}
            aria-hidden="true"
          />
          {t("costChart.legendOriginal")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: "var(--brand)" }}
            aria-hidden="true"
          />
          {t("costChart.legendRevised")}
        </span>
        {totalEligible > rows.length && (
          <span className="ml-auto">
            {t("costChart.sampleNote", {
              shown: rows.length,
              total: totalEligible.toLocaleString("en-IN"),
            })}
          </span>
        )}
      </div>
    </div>
  );
}
