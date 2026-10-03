export { ChartTooltip };


/**
 * Shared Recharts tooltip. Recharts' default tooltip is unthemed, so it
 * rendered as a white box on white cards and broke in dark mode once the
 * per-class dark remap was removed.
 */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-lg border border-line bg-overlay px-3 py-2 shadow-pop">
      {label != null && (
        <p className="mb-1 text-[11px] font-semibold text-fg-3">{label}</p>
      )}
      <ul className="space-y-0.5">
        {payload.map((entry) => (
          <li
            key={entry.dataKey ?? entry.name}
            className="flex items-center gap-2 text-xs"
          >
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ background: entry.color ?? entry.fill }}
            />
            <span className="text-fg-2">{entry.name}</span>
            <span className="ml-auto font-semibold tabular-nums text-fg">
              {typeof entry.value === "number"
                ? entry.value.toLocaleString("en-IN")
                : entry.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
