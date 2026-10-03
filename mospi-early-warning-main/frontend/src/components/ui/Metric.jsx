import { CountUp } from "./CountUp";

export { Metric };


function Metric({ label, value }) {
 return (
 <div className="rounded-xl bg-page p-3">
 <p className="text-[10px] uppercase tracking-wide text-fg-4">
 {label}
 </p>
 <p className="mt-1 truncate text-xs font-bold text-fg">
 <CountUp value={value} />
 </p>
 </div>
 );
}
