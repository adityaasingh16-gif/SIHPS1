export { Sparkline };

/**
 * Dependency-free SVG trend line for KPI tiles and briefs.
 *
 * Points are rendered as-is (no smoothing that could misread the data) and
 * the figure is labelled for screen readers. Static render: nothing to
 * disable under prefers-reduced-motion.
 */
function Sparkline({
  points = [],
  width = 120,
  height = 32,
  stroke = "var(--chart-1)",
  label = "trend",
}) {
  if (!points || points.length < 2) return null;
  const mx = Math.max(...points);
  const mn = Math.min(...points);
  const span = mx - mn || 1;
  const x = (i) => 2 + (i / (points.length - 1)) * (width - 4);
  const y = (v) => height - 3 - ((v - mn) / span) * (height - 8);
  const d = points
    .map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join(" ");
  const last = points[points.length - 1];
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label}
      className="overflow-visible"
    >
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={x(points.length - 1)} cy={y(last)} r={3} fill={stroke} />
    </svg>
  );
}
