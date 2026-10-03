import { useEffect, useState } from "react";
import { fetchConfusionMatrix } from "../../api";
import { useT } from "../../hooks/useT";

export { ConfusionMatrixCard };


// Tier names come back from the API as data; only the fallback list is
// translated, and it is keyed rather than compared so nothing depends on it.
const FALLBACK_CLASSES = [
  "common.low",
  "common.medium",
  "common.high",
  "common.critical",
];


function ConfusionMatrixCard() {
 const t = useT();
 const [data, setData] = useState(null);
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState(null);

 useEffect(() => {
 let mounted = true;
 fetchConfusionMatrix()
 .then((d) => mounted && setData(d))
 .catch((e) => mounted && setError(String(e?.message || e)))
 .finally(() => mounted && setLoading(false));
 return () => {
 mounted = false;
 };
 }, []);

 const classes = data?.classes || FALLBACK_CLASSES;
 const matrix = data?.matrix || [];
 const max = matrix.length ? Math.max(...matrix.flat()) : 1;
 const accuracy = data?.accuracy;

 // API classes are English tier names, so they need the same key lookup as
 // RiskBadge rather than being shown raw.
 const classLabel = (c) => {
  const i = FALLBACK_CLASSES.indexOf(c);
  if (i >= 0) return t(FALLBACK_CLASSES[i]);
  const byName = {
   Low: "common.low",
   Medium: "common.medium",
   High: "common.high",
   Critical: "common.critical",
  };
  return byName[c] ? t(byName[c]) : c;
 };

 return (
 <div className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
 <div className="mb-4 flex items-center justify-between">
 <div>
 <h3 className="font-bold text-fg">{t("matrix.title")}</h3>
 <p className="text-xs text-fg-3">{t("matrix.subtitle")}</p>
 </div>
    <span className="rounded-lg bg-brand-subtle px-3 py-1.5 text-xs font-semibold text-brand-subtle-fg">
 ML Core
 </span>
 </div>

 {loading ? (
 <div className="flex h-40 items-center justify-center text-sm text-fg-4">
 {t("matrix.evaluating")}
 </div>
 ) : error ? (
 <div className="flex h-40 items-center justify-center text-sm text-risk-critical">
 {error}
 </div>
 ) : (
 <>
 <div className="flex items-center">
 <div className="w-16 pr-1 sm:w-20">
 <span className="block text-[10px] font-semibold uppercase leading-tight tracking-wide text-fg-4">
 {t("matrix.actual")}
 </span>
 <span className="block text-[10px] font-semibold uppercase leading-tight tracking-wide text-fg-4">
 {t("matrix.arrowDown")}
 </span>
 </div>
 <div className="flex flex-1 gap-1">
 {classes.map((c) => (
 <div
 key={c}
 className="flex-1 truncate text-center text-[10px] font-bold text-fg-2 sm:text-xs"
 >
 {classLabel(c)}
 </div>
 ))}
 </div>
 </div>

 <div className="mt-1 space-y-1">
 {matrix.map((row, r) => (
 <div key={r} className="flex items-center gap-1">
 <div className="flex w-16 shrink-0 items-center pr-1 sm:w-20">
 <span className="w-full truncate text-right text-[10px] font-semibold text-fg-2 sm:text-xs">
 {classLabel(classes[r])}
 </span>
 </div>
 {row.map((cell, c) => {
 const ratio = max > 0 ? cell / max : 0;
 const isDiag = r === c;
 return (
 <div
 key={c}
 title={t("matrix.cellTitle", {
 actual: classLabel(classes[r]),
 predicted: classLabel(classes[c]),
 count: cell.toLocaleString(),
 })}
 className={`flex-1 rounded-lg border py-2 text-center text-[10px] font-bold sm:text-xs ${
 isDiag ?"border-brand" :"border-transparent"
 }`}
  style={{
  backgroundColor: `color-mix(in srgb, var(--brand) ${
  Math.round((0.08 + 0.9 * ratio) * 100)
  }%, var(--surface-raised))`,
  color: ratio > 0.5 ?"var(--brand-fg)" :"var(--fg-primary)",
  }}
 >
 {cell.toLocaleString()}
 </div>
 );
 })}
 </div>
 ))}
 </div>

 <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-fg-3">
 <span className="rounded-lg bg-sunken px-3 py-1.5 font-semibold text-fg-2">
 {t("matrix.accuracy", { pct: ((accuracy || 0) * 100).toFixed(1) })}
 </span>
 {data?.n_samples !== undefined && (
 <span>
 {t("matrix.evaluatedOn", { n: Number(data.n_samples).toLocaleString() })}
 </span>
 )}
 <span className="text-fg-4">{t("matrix.axisNote")}</span>
 </div>
 </>
 )}
 </div>
 );
}
