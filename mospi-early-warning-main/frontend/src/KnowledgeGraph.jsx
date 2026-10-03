import { useEffect, useMemo, useState } from"react";
import { Download, FileText, Network, RefreshCw, Search } from"lucide-react";
import { fetchGraphReport, fetchKnowledgeGraph } from"./api";
import { useT } from"./hooks/useT";

/**
 * Node/edge series colours, read from design tokens so the graph inverts
 * with the theme. These are SVG paint attributes, which resolve `var()`.
 * Ordered as a categorical set — distinct hues, not a single accent ramp,
 * because node type is the encoded variable here.
 */
const TYPE_COLORS = {
  project: "var(--chart-1)",
  ministry: "var(--chart-4)",
  sector: "var(--chart-2)",
  agency: "var(--chart-3)",
  risk: "var(--risk-critical)",
};

const EDGE_COLORS = {
  under_ministry: "var(--chart-4)",
  in_sector: "var(--chart-2)",
  implemented_by: "var(--chart-3)",
  driven_by: "var(--risk-critical)",
  shared_agency: "var(--chart-6)",
  shared_contractor: "var(--chart-5)",
};

const nodeKey = (n) => `${n.type}:${n.id}`;

function forceLayout(nodes, edges, W, H) {
 const pos = new Map(
 nodes.map((n) => [
 nodeKey(n),
 { x: W / 2 + (Math.random() - 0.5) * W * 0.45, y: H / 2 + (Math.random() - 0.5) * H * 0.45 },
 ]),
 );
 const index = new Map(nodes.map((n, i) => [nodeKey(n), i]));
 const springs = edges.map((e) => [index.get(e.source), index.get(e.target)]).filter(([a, b]) => a !== undefined && b !== undefined);

 for (let it = 0; it < 140; it++) {
 const forces = new Map(nodes.map((n, i) => [i, { fx: 0, fy: 0 }]));
 for (let i = 0; i < nodes.length; i++) {
 for (let j = i + 1; j < nodes.length; j++) {
 const a = pos.get(nodeKey(nodes[i]));
 const b = pos.get(nodeKey(nodes[j]));
 const dx = b.x - a.x;
 const dy = b.y - a.y;
 const d2 = Math.max(dx * dx + dy * dy, 36);
 const d = Math.sqrt(d2);
 const f = 2600 / d2;
 const ux = dx / d;
 const uy = dy / d;
 forces.get(i).fx -= ux * f;
 forces.get(i).fy -= uy * f;
 forces.get(j).fx += ux * f;
 forces.get(j).fy += uy * f;
 }
 }
 for (const [i, j] of springs) {
 const a = pos.get(nodeKey(nodes[i]));
 const b = pos.get(nodeKey(nodes[j]));
 const dx = b.x - a.x;
 const dy = b.y - a.y;
 const d = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
 const target = 88;
 const f = (d - target) * 0.028;
 const ux = dx / d;
 const uy = dy / d;
 forces.get(i).fx += ux * f;
 forces.get(i).fy += uy * f;
 forces.get(j).fx -= ux * f;
 forces.get(j).fy -= uy * f;
 }
 nodes.forEach((n, i) => {
 const p = pos.get(nodeKey(n));
 const f = forces.get(i);
 p.x += (f.fx * 0.12 + (W / 2 - p.x) * 0.008) * 0.5;
 p.y += (f.fy * 0.12 + (H / 2 - p.y) * 0.008) * 0.5;
 p.x = Math.max(8, Math.min(W - 8, p.x));
 p.y = Math.max(8, Math.min(H - 8, p.y));
 });
 }
 return pos;
}

export default function KnowledgeGraph({ setSelectedProject, setActive }) {
  const t = useT();
  const [graph, setGraph] = useState({ nodes: [], edges: [], meta: {} });
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState(null);
 const [filter, setFilter] = useState("");
 const [selected, setSelected] = useState(null);
 const [report, setReport] = useState(null);
 const [reportLoading, setReportLoading] = useState(false);

 const load = async () => {
 setLoading(true);
 setError(null);
 try {
 const data = await fetchKnowledgeGraph({ limit: 150 });
 setGraph(data || { nodes: [], edges: [], meta: {} });
 setSelected(null);
 } catch (e) {
  setError(e.message || t("graph.loading"));
 } finally {
 setLoading(false);
 }
 };

 useEffect(() => {
 load();
 }, []);

 const W = 900;
 const H = 640;

 const visibleNodes = useMemo(() => {
 const f = filter.trim().toLowerCase();
 return f ? graph.nodes.filter((n) => n.label.toLowerCase().includes(f) || String(n.id).toLowerCase().includes(f)) : graph.nodes;
 }, [graph.nodes, filter]);

 const visibleKeys = useMemo(() => new Set(visibleNodes.map(nodeKey)), [visibleNodes]);

 const visibleEdges = useMemo(
 () => graph.edges.filter((e) => visibleKeys.has(e.source) && visibleKeys.has(e.target)),
 [graph.edges, visibleKeys],
 );

 const pos = useMemo(() => forceLayout(visibleNodes, visibleEdges, W, H), [visibleNodes, visibleEdges]);

 const generateReport = async () => {
 setReportLoading(true);
 try {
 const data = await fetchGraphReport({ limit: 100 });
 setReport(data);
 } catch (e) {
  setReport({ title: t("graph.reportErrorTitle"), sections: [{ heading: t("graph.reportErrorHeading"), body: String(e.message || e) }] });
 } finally {
 setReportLoading(false);
 }
 };

 const selectedNode = graph.nodes.find((n) => nodeKey(n) === selected);

 return (
 <div className="space-y-6">
 <div className="flex flex-wrap items-end justify-between gap-4">
 <div>
 <h1 className="flex items-center gap-2 text-2xl font-bold text-fg">
  <Network className="h-6 w-6 text-brand" /> {t("graph.title")}
  </h1>
  <p className="mt-1 text-sm text-fg-3">
  {t("graph.subtitle")}
  <span className="font-medium text-fg-2">
  {" "}
  {t("graph.counts", {
  projects: graph.meta.projects ?? 0,
  nodes: graph.meta.nodes ?? 0,
  edges: graph.meta.edges ?? 0,
  })}
  </span>
  </p>
 </div>
 <div className="flex flex-wrap items-center gap-2">
 <div className="relative min-w-[9rem] flex-1 sm:flex-none">
 <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-4" />
 <input
  value={filter}
  onChange={(e) => setFilter(e.target.value)}
   placeholder={t("graph.filterPlaceholder")}
  className="w-full rounded-lg border border-line bg-raised pl-8 pr-3 py-2 text-sm outline-none focus:border-brand sm:w-56"
 />
 </div>
 <button
  type="button"
  onClick={load}
  className="flex shrink-0 items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm text-fg-2 hover:bg-page :bg-fg"
 >
  <RefreshCw className="h-4 w-4" /> {t("graph.reload")}
 </button>
 <button
 type="button"
 onClick={generateReport}
 disabled={reportLoading}
  className="flex shrink-0 items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-sm text-white hover:bg-brand-hover disabled:opacity-50"
 >
  <FileText className="h-4 w-4" /> {reportLoading ? t("graph.generating") : t("graph.generateReport")}
 </button>
 </div>
 </div>

 <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
 <div className="relative rounded-2xl border border-line bg-page p-2">
 {loading ? (
  <div className="flex h-[640px] items-center justify-center text-sm text-fg-4">{t("graph.loading")}</div>
 ) : error ? (
 <div className="flex h-[640px] items-center justify-center text-sm text-risk-critical">{error}</div>
 ) : visibleNodes.length === 0 ? (
  <div className="flex h-[640px] items-center justify-center text-sm text-fg-4">{t("graph.noMatches")}</div>
 ) : (
 <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
 {visibleEdges.map((e, i) => (
 <line
 key={i}
 x1={pos.get(e.source)?.x}
 y1={pos.get(e.source)?.y}
 x2={pos.get(e.target)?.x}
 y2={pos.get(e.target)?.y}
 stroke={EDGE_COLORS[e.type] ||"var(--line-heavy)"}
 strokeWidth={1}
 opacity={0.45}
 />
 ))}
 {visibleNodes.map((n) => {
 const p = pos.get(nodeKey(n));
 if (!p) return null;
 const r = n.type ==="project" ? 9 : 6;
 const isSel = selected === nodeKey(n);
 return (
 <g
 key={nodeKey(n)}
 transform={`translate(${p.x},${p.y})`}
 onClick={() => setSelected(isSel ? null : nodeKey(n))}
 style={{ cursor:"pointer" }}
 >
 <circle r={isSel ? r + 4 : r} fill={TYPE_COLORS[n.type] ||"var(--line-heavy)"} stroke={isSel ?"var(--surface-page)" :"var(--surface-raised)"} strokeWidth={1.5} />
 <title>{n.label}</title>
 <text
 y={-r - 4}
 textAnchor="middle"
 fontSize={9}
 fill="var(--fg-muted)"
 className="pointer-events-none select-none"
 >
 {n.type ==="project" ? n.id : n.label.length > 26 ? `${n.label.slice(0, 25)}…` : n.label}
 </text>
 </g>
 );
 })}
 </svg>
 )}
 {selectedNode && (
 <div className="absolute right-3 top-3 w-72 rounded-xl border border-line bg-raised p-4 shadow-lg">
  <p className="text-xs font-semibold uppercase tracking-wide text-fg-4">{t(`graph.type.${selectedNode.type}`)}</p>
 <p className="mt-1 text-sm font-semibold text-fg">{selectedNode.label}</p>
 <dl className="mt-3 space-y-1.5 text-xs text-fg-2">
 {Object.entries(selectedNode.meta || {}).map(([k, v]) => (
 <div key={k} className="flex justify-between gap-2">
 <dt className="capitalize text-fg-4">{k.replace(/_/g,"")}</dt>
 <dd className="text-right font-medium">{typeof v ==="number" ? v.toLocaleString() : String(v)}</dd>
 </div>
 ))}
 </dl>
 {selectedNode.type ==="project" && (
 <button
 type="button"
 onClick={() => {
 setSelectedProject?.(selectedNode.id);
 setActive?.("projects");
 }}
 className="mt-3 w-full rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white hover:bg-brand-hover"
 >
   {t("graph.openProject", { id: selectedNode.id })}
   </button>
 )}
 </div>
 )}
 </div>

 <div className="space-y-4">
 <div className="rounded-2xl border border-line p-4">
  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-4">{t("graph.legend")}</p>
  <div className="space-y-1.5 text-xs text-fg-2">
  {Object.entries(TYPE_COLORS).map(([typeKey, c]) => (
  <div key={typeKey} className="flex items-center gap-2">
  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: c }} />
  <span>{t(`graph.type.${typeKey}`)}</span>
  </div>
  ))}
 </div>
 </div>

 {report && (
 <div className="rounded-2xl border border-line bg-raised p-4">
 <div className="mb-3 flex items-center justify-between">
 <p className="text-sm font-bold text-fg">{report.title}</p>
 <button
 type="button"
 onClick={() => setReport(null)}
 className="text-xs text-fg-4 hover:text-fg-2"
   aria-label={t("graph.closeReport")}
 >
 ✕
 </button>
 </div>
 <div className="space-y-3 text-xs text-fg-2">
 {(report.sections || []).map((s, i) => (
 <div key={i}>
 <p className="mb-1 font-semibold text-fg-2">{s.heading}</p>
 <p className="whitespace-pre-wrap leading-relaxed">{s.body}</p>
 </div>
 ))}
 </div>
 <a
 href="/api/graph/report.html"
 target="_blank"
 rel="noreferrer"
 className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-xs text-fg-2 hover:bg-page :bg-fg"
 >
  <Download className="h-3.5 w-3.5" /> {t("graph.openPrintable")}
 </a>
 </div>
 )}
 </div>
 </div>
 </div>
 );
}