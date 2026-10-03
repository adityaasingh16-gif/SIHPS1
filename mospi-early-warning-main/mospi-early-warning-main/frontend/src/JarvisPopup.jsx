import { useCallback, useEffect, useRef, useState } from"react";
import { Bot, GripHorizontal, ShieldAlert, X } from"lucide-react";
import { fetchAlerts } from"./api";
import { useT } from"./hooks/useT";

const SEVERITY_STYLE = {
 Critical:"bg-risk-critical-subtle text-risk-critical",
 High:"bg-risk-high-subtle text-risk-high",
 Warning:"bg-risk-medium-subtle text-risk-medium",
};

function loadPos() {
 try {
 const raw = localStorage.getItem("jarvis-pos");
 if (raw) {
 const p = JSON.parse(raw);
 if (typeof p.x ==="number" && typeof p.y ==="number") return p;
 }
 } catch {
 /* ignore */
 }
 return { x: 20, y: window.innerHeight - 430 };
}

export default function JarvisPopup({ backendOnline, setActive }) {
 const t = useT();
 const [open, setOpen] = useState(false);
 const [pos, setPos] = useState(loadPos);
 const posRef = useRef(pos);
 const [alerts, setAlerts] = useState([]);
 const [loaded, setLoaded] = useState(false);
 const timer = useRef(null);

 useEffect(() => {
 const load = () =>
 fetchAlerts()
 .then((data) => {
 if (Array.isArray(data)) setAlerts(data);
 setLoaded(true);
 })
 .catch(() => setLoaded(true));
 load();
 timer.current = setInterval(load, 60000);
 return () => clearInterval(timer.current);
 }, []);

 const startDrag = useCallback(
 (e) => {
 if (e.button !== undefined && e.button !== 0) return;
 const sx = e.clientX;
 const sy = e.clientY;
 const ox = posRef.current.x;
 const oy = posRef.current.y;
 const pad = open ? 400 : 230;
 const onMove = (ev) => {
 const x = Math.max(4, Math.min(window.innerWidth - pad, ox + ev.clientX - sx));
 const y = Math.max(4, Math.min(window.innerHeight - 40, oy + ev.clientY - sy));
 posRef.current = { x, y };
 setPos({ x, y });
 };
 const onUp = () => {
 window.removeEventListener("pointermove", onMove);
 window.removeEventListener("pointerup", onUp);
 try {
 localStorage.setItem("jarvis-pos", JSON.stringify(posRef.current));
 } catch {
 /* ignore */
 }
 };
 window.addEventListener("pointermove", onMove);
 window.addEventListener("pointerup", onUp);
 },
 [open],
 );

 const critical = alerts.filter((a) => a.severity ==="Critical").length;
 const top = alerts.slice(0, 8);
 const hasAny = alerts.length > 0;

 return (
 <>
 <div
 role="button"
 tabIndex={0}
  aria-label={open ?t("jarvis.alerts") :t("jarvis.handle")}
  title={t("jarvis.handle")}
 onClick={() => setOpen((o) => !o)}
 onKeyDown={(e) => e.key ==="Enter" && setOpen((o) => !o)}
 onPointerDown={startDrag}
 className="fixed z-50 flex w-[210px] touch-none select-none items-center gap-2 rounded-full border border-line bg-raised py-2 pl-3 pr-4 shadow-lg shadow-fg/10 transition-transform hover:scale-[1.03]"
 style={{ left: pos.x, top: pos.y, cursor:"grab" }}
 >
    <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand to-brand-active text-white">
 {hasAny ? (
 <>
 <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-40" />
 <Bot className="h-4 w-4" />
 </>
 ) : (
 <Bot className="h-4 w-4" />
 )}
 </span>
 <span className="text-left">
 <span className="block text-xs font-bold text-fg">{t("jarvis.name")}</span>
 <span className="block text-[10px] text-fg-3">
 {!backendOnline
 ?t("jarvis.offline")
 : !loaded
 ?t("jarvis.scanning")
 : hasAny
 ?t("jarvis.alertsSummary", { n: alerts.length, c: critical })
 :t("jarvis.noActiveAlerts")}
 </span>
 </span>
 {hasAny && (
 <span className="ml-1 rounded-full bg-risk-critical px-1.5 py-0.5 text-[10px] font-bold text-white">{alerts.length}</span>
 )}
 <GripHorizontal className="h-3.5 w-3.5 text-line-strong" />
 </div>

 {open && (
 <aside
 role="dialog"
 aria-label={t("jarvis.alerts")}
 className="fixed z-50 flex max-h-[70vh] w-[calc(100vw-2.5rem)] max-w-sm flex-col overflow-hidden rounded-2xl border border-line bg-raised shadow-2xl"
 style={{ left: pos.x, top: pos.y + 54 }}
 >
 <header
 onPointerDown={startDrag}
 className="flex cursor-grab touch-none select-none items-center gap-3 border-b border-line bg-gradient-to-r from-fg to-brand-active px-4 py-3 text-white"
 >
 <span className="flex h-9 w-9 items-center justify-center rounded-full bg-raised/15">
 <Bot className="h-5 w-5" />
 </span>
 <div className="flex-1">
 <p className="text-sm font-semibold">{t("jarvis.riskSentinel")}</p>
 <p className="text-[11px] text-white/70">
 {hasAny
 ?t("jarvis.watching", { n: alerts.length })
 :t("jarvis.allClear")}
 </p>
 </div>
 <GripHorizontal className="h-4 w-4 text-white/40" />
 <button
 type="button"
 onClick={() => setOpen(false)}
 className="rounded-lg p-1.5 text-white/70 hover:bg-raised/15"
 aria-label={t("jarvis.close")}
 >
 <X className="h-4 w-4" />
 </button>
 </header>

 <div className="flex-1 space-y-2 overflow-y-auto p-3">
 {!backendOnline ? (
 <p className="px-1 py-4 text-center text-xs text-fg-3">{t("jarvis.backendOffline")}</p>
 ) : !loaded ? (
 <p className="px-1 py-4 text-center text-xs text-fg-3">{t("jarvis.scanningFeed")}</p>
 ) : top.length === 0 ? (
 <p className="px-1 py-4 text-center text-xs text-fg-3">{t("jarvis.empty")}</p>
 ) : (
 top.map((a) => (
 <div key={a.id} className="rounded-xl border border-line bg-page p-2.5">
 <div className="flex items-center justify-between gap-2">
 <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${SEVERITY_STYLE[a.severity] ||"bg-hover text-fg-2"}`}>
 {a.severity}
 </span>
 <span className="text-[10px] text-fg-4">
 {t("jarvis.scoreLabel", {
 tier: a.risk_tier,
 score:
  typeof a.composite_risk_score ==="number"
   ? a.composite_risk_score.toFixed(1)
   : a.composite_risk_score,
 })}
 </span>
 </div>
 <p className="mt-1.5 text-xs text-fg-2">{a.message}</p>
 </div>
 ))
 )}
 </div>

 {hasAny && (
 <footer className="border-t border-line p-3">
 <button
 type="button"
 onClick={() => {
 setOpen(false);
 setActive("warnings");
 }}
 className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white hover:bg-brand-hover"
 >
 <ShieldAlert className="h-3.5 w-3.5" /> {t("jarvis.viewAll")}
 </button>
 </footer>
 )}
 </aside>
 )}
 </>
 );
}