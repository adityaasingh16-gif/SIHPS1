import { useEffect, useState } from "react";
import { fetchRiskStatus } from "../../api";
import { useT } from "../../hooks/useT";

export { RiskFreshness };

function RiskFreshness({ compact = false }) {
 const t = useT();
 const [status, setStatus] = useState(null);
 const [now, setNow] = useState(Date.now());

 useEffect(() => {
 let mounted = true;
 const tick = () => {
 fetchRiskStatus()
 .then((d) => mounted && setStatus(d))
 .catch(() => {});
 };
 tick();
 const int = setInterval(tick, 30000);
 const nowInt = setInterval(() => setNow(Date.now()), 15000);
 return () => {
 mounted = false;
 clearInterval(int);
 clearInterval(nowInt);
 };
 }, []);

 if (!status?.last_synced_at) return null;

 const secs = Math.max(0, (now - new Date(status.last_synced_at).getTime()) / 1000);
 const mins = Math.floor(secs / 60);
 const label =
  mins < 1
   ? t("freshness.justNow")
   : mins < 60
    ? t("freshness.minutesAgo", { n: mins })
    : t("freshness.hoursAgo", { h: Math.floor(mins / 60), m: mins % 60 });
 const idle = secs > status.interval_seconds * 2;

 return (
 <span
 title={
  status.summary
   ? t("freshness.lastAutoSync", {
    scanned: status.summary.scanned,
    changed: status.summary.tiers_changed,
    })
   : t("freshness.liveAutoRefresh")
 }
 className={`inline-flex items-center gap-1.5 rounded-lg border text-xs font-medium ${
 compact
 ?"border-risk-low-border bg-risk-low-subtle px-2 py-1 text-risk-low"
 :"border-risk-low-border bg-risk-low-subtle px-3 py-1.5 text-risk-low"
 }`}
 >
 <span className="relative flex h-2 w-2">
 <span
 className={`absolute inline-flex h-full w-full animate-ping rounded-full ${idle ?"bg-risk-medium" :"bg-risk-low"} opacity-75`}
 />
 <span
 className={`relative inline-flex h-2 w-2 rounded-full ${idle ?"bg-risk-medium" :"bg-risk-low"}`}
 />
 </span>
 {t("freshness.autoSync", { when: label })}
 </span>
 );
}
