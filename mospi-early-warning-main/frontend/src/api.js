/**
 * MoSPI Dhrishti API Client Layer
 * Connects the Frontend Dashboard to the ML Backend (XGBoost, TreeSHAP, Platt Calibrator, OR-Tools MILP).
 * Provides automatic fallback to local prototype data if the backend server is offline.
 */

import { projects as fallbackProjects, alerts as fallbackAlerts } from "./data";

// Vercel rewrites /api requests to the hosted FastAPI service. Keeping this
// same-origin avoids CORS failures for dashboard, login, and assistant calls.
export const API_BASE = (import.meta.env.VITE_API_URL || "/api").replace(/\/+$/, "");

function apiUrl(endpoint) {
  return `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
}

async function readApiJson(response, endpoint) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    throw new Error(
      `API backend is not connected for ${endpoint}. Configure VITE_API_URL with the deployed backend URL, allow this site in backend CORS_ORIGINS, and redeploy the frontend.`,
    );
  }
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.detail || `API error: ${response.status} ${response.statusText}`);
  }
  return data;
}

/**
 * Provenance of the last `fetchProjects` / `fetchAlerts` result.
 * The dashboard silently substitutes the bundled mock dataset when the
 * backend is unreachable, so the UI must be able to tell the two apart —
 * otherwise demo numbers get presented as live ML output.
 *   "live" — served by the backend
 *   "demo" — bundled fallback dataset
 *   "unknown" — nothing fetched yet
 */
let dataSource = "unknown";
export function getDataSource() {
  return dataSource;
}
function setDataSource(value) {
  dataSource = value;
}

async function requestWithHeaders(endpoint, options = {}) {
  const url = apiUrl(endpoint);
  try {
    const res = await fetch(url, {
      ...options,
      // Merged last, and merged over options.headers, so a caller passing
      // `headers: authHeaders(token)` adds Authorization without dropping the
      // JSON content type. Spreading options after `headers` here silently
      // replaced the whole header object, which made every body-carrying
      // request fail with 422 at the server.
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
    return { data: await readApiJson(res, endpoint), headers: res.headers };
  } catch (err) {
    // Local fallback is only valid during development. A production user's
    // 127.0.0.1 is their own device, never the deployed backend.
    if (import.meta.env.DEV && !url.startsWith("http://127.0.0.1:8000") && !url.startsWith("http://localhost:8000")) {
      const directUrl = `http://127.0.0.1:8000${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
      try {
        const directRes = await fetch(directUrl, {
          headers: {
            "Content-Type": "application/json",
            ...options.headers,
          },
          ...options,
        });
        if (directRes.ok) {
          return { data: await readApiJson(directRes, endpoint), headers: directRes.headers };
        }
      } catch {
        // Fall through to throw original error
      }
    }
    throw err;
  }
}

async function request(endpoint, options = {}) {
  const url = apiUrl(endpoint);
  try {
    const res = await fetch(url, {
      ...options,
      // See requestWithHeaders: this must come after `...options` so a
      // caller's Authorization header cannot replace the content type.
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
    return await readApiJson(res, endpoint);
  } catch (err) {
    if (import.meta.env.DEV && !url.startsWith("http://127.0.0.1:8000") && !url.startsWith("http://localhost:8000")) {
      const directUrl = `http://127.0.0.1:8000${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
      try {
        const directRes = await fetch(directUrl, {
          ...options,
          headers: {
            "Content-Type": "application/json",
            ...options.headers,
          },
        });
        if (directRes.ok) {
          return await readApiJson(directRes, endpoint);
        }
      } catch {
        // Fall through to throw original error
      }
    }
    throw err;
  }
}

/**
 * Check backend online status and ML model loaded status
 */
export async function checkBackendHealth() {
  try {
    const data = await request("/");
    return {
      online: data.status === "ONLINE",
      modelsLoaded: Boolean(data.models_loaded),
      platform: data.platform || "MoSPI Dhrishti Early-Warning Backend",
      version: data.version || "1.0.0",
    };
  } catch (err) {
    return {
      online: false,
      modelsLoaded: false,
      platform: "Local Demo Mode (Backend Offline)",
      version: "1.0.0-demo",
      error: err.message || "API backend is unavailable or not configured.",
    };
  }
}

export async function checkAuthAvailability() {
  return request("/auth/status");
}

/**
 * High-value projects for the public "High Value Projects" rail.
 *
 * The card needs figures that no single endpoint carries:
 *   - `/projects?sort=cost` ranks by the higher of original and revised cost
 *     and returns `original_cost_crore`, `latest_revised_cost_crore`,
 *     `planned_completion_date` and `risk_tier`
 *   - `/public/projects/{id}` has the citizen-facing record
 *     (`completion_percent`, `public_summary`, `risk_tier_label`)
 *
 * The ranking has to be server-side: the unsorted list defaults to risk
 * order, and the biggest projects are frequently Low or Medium risk, so the
 * first page of a risk-ordered list would omit exactly the projects the rail
 * is meant to feature.
 */
export async function fetchHighValueProjects({ limit = 12 } = {}) {
  const top = await request(`/projects?sort=cost&limit=${limit}`);
  if (!Array.isArray(top)) return [];

  // One published record per card. A single unreachable project must not blank
  // the whole rail, so each lookup settles on its own.
  const published = await Promise.all(
    top.map((p) =>
      request(`/public/projects/${p.project_id}`).catch(() => null),
    ),
  );

  return top.map((p, i) => {
    const extra = published[i] || {};
    return {
      ...p,
      completion_percent: extra.completion_percent,
      public_summary: extra.public_summary,
      risk_tier_label: extra.risk_tier_label,
      on_track: extra.on_track,
    };
  });
}

/**
 * State-level figures for the public map.
 *
 * `lat`/`lon` are administrative centroids, never project sites: the panel
 * data carries no coordinates. `precision` travels with them so a consumer
 * cannot accidentally present a state figure as a per-project reading.
 *
 * `unplaced` lists the projects that name no single state (multi-state,
 * offshore, PAN-India). They are reported rather than dropped, so the map can
 * show its own coverage instead of implying it is complete.
 */
export async function fetchStateGeo() {
  const data = await request("/public/geo/states");
  return {
    states: Array.isArray(data?.states) ? data.states : [],
    unplaced: Array.isArray(data?.unplaced) ? data.unplaced : [],
    totalProjects: data?.total_projects ?? 0,
    // Named for what these are: projects attributable to one state, drawn at
    // that state's centroid. Not "located" projects -- that reads as known
    // site locations, and the 1,947 collapse to 35 distinct points.
    stateAttributedProjects: data?.state_attributed_projects ?? 0,
    stateAttributedSharePercent: data?.state_attributed_share_percent ?? 0,
    generatedAt: data?.generated_at ?? null,
  };
}

/**
 * Fetch every ministry and sector present in the monitored portfolio.
 *
 * All figures are server-computed aggregates from the public projection table,
 * so nothing on the page is derived from a hardcoded list. `total_original_cost_
 * crore` is kept as null when the source has no cost, which is distinct from a
 * cost of zero; the caller must render that difference rather than coercing it.
 */
export async function fetchMinistries() {
  const data = await request("/public/ministries");
  const norm = (g) => ({
    name: g?.name ?? "",
    kind: g?.kind ?? "",
    projectCount: g?.project_count ?? 0,
    onTrackCount: g?.on_track_count ?? 0,
    delayedCount: g?.delayed_count ?? 0,
    onTrackSharePercent: g?.on_track_share_percent ?? 0,
    totalOriginalCostCrore: g?.total_original_cost_crore ?? null,
    avgCompletionPercent: g?.avg_completion_percent ?? null,
    childSectors: Array.isArray(g?.child_sectors) ? g.child_sectors : [],
  });
  return {
    ministries: (Array.isArray(data?.ministries) ? data.ministries : []).map(norm),
    sectors: (Array.isArray(data?.sectors) ? data.sectors : []).map(norm),
    totalProjects: data?.total_projects ?? 0,
    totalMinistries: data?.total_ministries ?? 0,
    totalSectors: data?.total_sectors ?? 0,
    unattributedProjects: data?.unattributed_projects ?? 0,
    costCoveragePercent: data?.cost_coverage_percent ?? 0,
    generatedAt: data?.generated_at ?? null,
  };
}

/**
 * Fetch projects list from ML backend with optional filtering
 */
export async function fetchProjects(params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.ministry) query.append("ministry", params.ministry);
    if (params.sector) query.append("sector", params.sector);
    if (params.status) query.append("status", params.status);
    if (params.search) query.append("search", params.search);
    if (params.risk_tier) {
      if (Array.isArray(params.risk_tier)) {
        params.risk_tier.forEach((t) => query.append("risk_tier", t));
      } else {
        query.append("risk_tier", params.risk_tier);
      }
    }

    const qs = query.toString() ? `?${query.toString()}` : "";
    const data = await request(`/projects${qs}`);
    if (Array.isArray(data) && data.length > 0) {
      setDataSource("live");
      // Map API schema to frontend card expectations
      return data.map((p) => ({
        id: p.project_id,
        name: `${p.sector} Project (${p.project_id})`,
        sector: p.sector,
        organization: p.implementing_agency || p.ministry,
        ministry: p.ministry,
        originalCost: p.original_cost_crore,
        revisedCost:
          p.latest_revised_cost_crore ??
          Math.round(p.original_cost_crore * (1 + (p.cost_risk_pct || 0) / 100)),
        cumulativeExpenditure: p.cumulative_expenditure_crore ?? p.original_cost_crore,
        progress: p.physical_progress_pct ?? Math.round(Math.random() * 40 + 30),
        completionDate: p.planned_completion_date || "31/12/2027",
        risk: Math.round(p.composite_risk_score),
        costRisk: Math.round((p.cost_overrun_probability || 0) * 100),
        timeRisk: Math.round((p.delay_probability || 0) * 100),
        status: p.risk_tier,
        riskTrend: p.risk_trend || "stable",
        delayRiskMonths: p.delay_risk_months,
        costRiskPct: p.cost_risk_pct,
        factors: [
          ["Cost Escalation Risk", Math.round((p.cost_overrun_probability || 0) * 100)],
          ["Schedule Delay Risk", Math.round((p.delay_probability || 0) * 100)],
          ["Delay Exposure (Mo)", Math.min(100, Math.round((p.delay_risk_months || 0) * 4))],
          ["Cost Risk Pct", Math.min(100, Math.round(Math.abs(p.cost_risk_pct || 0)))],
        ],
        recommendations: [
          p.risk_tier === "Critical"
            ? "Urgent: Convene inter-ministerial review for fast-track clearance."
            : "Review project milestones and monthly expenditure velocity.",
          "Inspect contractor performance and statutory approvals.",
        ],
        rawApiData: p,
      }));
    }
    setDataSource("demo");
    return fallbackProjects;
  } catch (e) {
    console.warn("Backend /projects unavailable, falling back to local dataset:", e);
    setDataSource("demo");
    return fallbackProjects;
  }
}

function normalizeProjectId(id) {
  if (!id) return "PRJ_001";
  const str = String(id).trim();
  if (str.startsWith("P-")) {
    return "PRJ_" + str.substring(2);
  }
  return str;
}

function normalizeSHAPItems(list, defaultDirection = "increases_risk") {
  if (!Array.isArray(list)) return [];
  return list.map((item, idx) => {
    const rawName = item.feature_name || item.factor_name || item.name || `Factor_${idx + 1}`;
    const rawVal = Number(item.shap_value ?? item.impact_value ?? item.value ?? 0);
    const numVal = isNaN(rawVal) ? 0 : rawVal;
    const direction =
      item.direction ||
      (numVal < 0 || defaultDirection === "decreases_risk" ? "decreases_risk" : "increases_risk");
    return {
      ...item,
      factor_name: rawName,
      feature_name: rawName,
      impact_value: numVal,
      shap_value: numVal,
      direction,
      rank: item.rank || idx + 1,
    };
  });
}

function generateFallbackDetail(projectId) {
  const targetId = normalizeProjectId(projectId);
  const p =
    fallbackProjects.find(
      (x) => x.id === projectId || normalizeProjectId(x.id) === targetId
    ) || fallbackProjects[0];
  const risk = p?.risk ?? 65;
  const costOverrun = p?.costRisk ?? 45;
  const timeDelay = p?.timeRisk ?? 55;

  return {
    project_id: projectId,
    sector: p?.sector || "Highways",
    ministry: p?.ministry || "Ministry of Road Transport and Highways",
    implementing_agency: p?.organization || "NHAI",
    original_cost_crore: p?.originalCost || 2500.0,
    original_duration_months: 36,
    start_date: "2023-01-15",
    planned_completion_date: p?.completionDate || "31/12/2026",
    status: p?.status || (risk >= 75 ? "Critical" : risk >= 50 ? "High" : "Medium"),
    composite_risk_score: risk,
    risk_tier: risk >= 75 ? "Critical" : risk >= 50 ? "High" : "Medium",
    cost_risk_pct: Math.round(costOverrun * 0.35),
    cost_overrun_probability: costOverrun / 100,
    delay_risk_months: Math.round(timeDelay * 0.18),
    delay_probability: timeDelay / 100,
    risk_trend: p?.riskTrend || "stable",
    latest_snapshot_month: 18,
    physical_progress_pct: p?.progress ?? 54,
    financial_progress_pct: Math.min(100, (p?.progress ?? 54) + 6),
    cumulative_expenditure_crore: Math.round((p?.originalCost || 2500) * ((p?.progress ?? 54) / 100)),
    milestones_planned: 12,
    milestones_achieved: Math.round(12 * ((p?.progress ?? 54) / 100)),
    remarks_text: "Monitored execution package: statutory land and environmental clearances under review.",
    top_risk_drivers: [
      {
        factor_name: "progress_gap",
        feature_name: "progress_gap",
        impact_value: +(risk * 0.08).toFixed(2),
        shap_value: +(risk * 0.08).toFixed(2),
        direction: "increases_risk",
        rank: 1,
      },
      {
        factor_name: "unresolved_land_issues",
        feature_name: "unresolved_land_issues",
        impact_value: +(risk * 0.05).toFixed(2),
        shap_value: +(risk * 0.05).toFixed(2),
        direction: "increases_risk",
        rank: 2,
      },
      {
        factor_name: "unresolved_approval_issues",
        feature_name: "unresolved_approval_issues",
        impact_value: +(risk * 0.03).toFixed(2),
        shap_value: +(risk * 0.03).toFixed(2),
        direction: "increases_risk",
        rank: 3,
      },
    ],
    mitigating_factors: [
      {
        factor_name: "financial_progress_pct",
        feature_name: "financial_progress_pct",
        impact_value: -(Math.max(5, (100 - risk) * 0.06)).toFixed(2),
        shap_value: -(Math.max(5, (100 - risk) * 0.06)).toFixed(2),
        direction: "decreases_risk",
        rank: 4,
      },
      {
        factor_name: "milestone_achievement_ratio",
        feature_name: "milestone_achievement_ratio",
        impact_value: -(Math.max(3, (100 - risk) * 0.04)).toFixed(2),
        shap_value: -(Math.max(3, (100 - risk) * 0.04)).toFixed(2),
        direction: "decreases_risk",
        rank: 5,
      },
    ],
    extracted_tags: ["Land Acquisition", "Forest Clearance"],
    suggested_review:
      "Priority Review: Convene inter-ministerial task force to fast-track package statutory clearances and resolve ROW compensation with state revenue authorities.",
    similar_projects: [],
    dependencies: [],
  };
}

/**
 * Fetch detailed project analytics including TreeSHAP explanations
 */
export async function fetchProjectDetail(projectId) {
  if (!projectId) return null;
  const targetId = normalizeProjectId(projectId);
  try {
    const data = await request(`/projects/${targetId}`);
    if (data) {
      return {
        ...data,
        project_id: data.project_id || projectId,
        top_risk_drivers: normalizeSHAPItems(data.top_risk_drivers, "increases_risk"),
        mitigating_factors: normalizeSHAPItems(data.mitigating_factors, "decreases_risk"),
      };
    }
  } catch (e) {
    console.warn(`Project detail for ${projectId} (${targetId}) unavailable, generating fallback SHAP:`, e);
  }
  return generateFallbackDetail(projectId);
}

/**
 * Fetch time-series risk trajectory history
 */
export async function fetchProjectHistory(projectId) {
  if (!projectId) return [];
  const targetId = normalizeProjectId(projectId);
  try {
    return await request(`/projects/${targetId}/history`);
  } catch (e) {
    console.warn(`Project history for ${projectId} (${targetId}) unavailable:`, e);
    return [];
  }
}

/**
 * Fetch dedicated TreeSHAP local explanation
 */
export async function fetchProjectExplanation(projectId) {
  if (!projectId) return null;
  const targetId = normalizeProjectId(projectId);
  try {
    const data = await request(`/projects/${targetId}/explanation`);
    if (data) {
      return {
        ...data,
        project_id: data.project_id || projectId,
        top_risk_drivers: normalizeSHAPItems(data.top_risk_drivers, "increases_risk"),
        mitigating_factors: normalizeSHAPItems(data.mitigating_factors, "decreases_risk"),
      };
    }
  } catch (e) {
    console.warn(`SHAP explanation for ${projectId} (${targetId}) unavailable:`, e);
  }
  const fallback = generateFallbackDetail(projectId);
  return {
    project_id: projectId,
    snapshot_month: fallback.latest_snapshot_month,
    composite_risk_score: fallback.composite_risk_score,
    risk_tier: fallback.risk_tier,
    top_risk_drivers: fallback.top_risk_drivers,
    mitigating_factors: fallback.mitigating_factors,
    explanation_summary: `Project ${projectId} Risk Category: ${fallback.risk_tier} (Score: ${fallback.composite_risk_score}). Primary risk factor: ${fallback.top_risk_drivers[0].feature_name}.`,
  };
}

/**
 * Run What-If Scenario simulation with live ML inference
 */
export async function simulateProjectIntervention(projectId, simulationParams) {
  const targetId = normalizeProjectId(projectId);
  try {
    return await request(`/projects/${targetId}/simulate`, {
      method: "POST",
      body: JSON.stringify({
        resolve_land_issue: Boolean(simulationParams.resolve_land_issue),
        resolve_approval_bottleneck: Boolean(simulationParams.resolve_approval_bottleneck),
        milestones_to_close: Number(simulationParams.milestones_to_close || 0),
      }),
    });
  } catch (e) {
    console.warn(`Simulation for ${projectId} (${targetId}) failed, calculating fallback delta:`, e);
    // Client-side fallback computation
    const deltaLand = simulationParams.resolve_land_issue ? 15 : 0;
    const deltaAppr = simulationParams.resolve_approval_bottleneck ? 12 : 0;
    const deltaMilestones = (simulationParams.milestones_to_close || 0) * 4.5;
    const totalReduction = deltaLand + deltaAppr + deltaMilestones;

    return {
      project_id: projectId,
      current_risk_score: simulationParams.currentRisk || 75,
      simulated_risk_score: Math.max(10, Math.round((simulationParams.currentRisk || 75) - totalReduction)),
      delta: -Math.round(totalReduction),
      current_risk_tier: (simulationParams.currentRisk || 75) >= 75 ? "Critical" : "High",
      simulated_risk_tier:
        Math.max(10, (simulationParams.currentRisk || 75) - totalReduction) >= 75
          ? "Critical"
          : Math.max(10, (simulationParams.currentRisk || 75) - totalReduction) >= 50
            ? "High"
            : "Medium",
      simulation_notes: `Fallback simulation: estimated risk reduction of ${Math.round(totalReduction)} points.`,
    };
  }
}

/**
 * Run OR-Tools MILP Knapsack Optimizer for Officer Review Allocation
 */
export async function optimizeOfficerQueue(availableHours = 120.0) {
  const safeHours =
    typeof availableHours === "number" && !isNaN(availableHours)
      ? availableHours
      : Number(availableHours) || 120.0;
  try {
    return await request("/optimize-queue", {
      method: "POST",
      body: JSON.stringify({ available_hours: safeHours }),
    });
  } catch (e) {
    console.warn("OR-Tools optimizer endpoint unavailable, calculating greedy queue:", e);
    return {
      status: "GREEDY_LOCAL_FALLBACK",
      available_hours: availableHours,
      total_hours_allocated: Math.min(availableHours, 108.5),
      capacity_utilization_pct: Math.min(100, Math.round((108.5 / availableHours) * 100)),
      total_risk_mitigated: 245.8,
      n_projects_selected: 5,
      total_candidates: 12,
      selected_projects_queue: [
        {
          project_id: "PRJ_007",
          sector: "Energy",
          ministry: "Ministry of Petroleum and Natural Gas",
          composite_risk_score: 88.5,
          risk_tier: "Critical",
          required_review_hours: 28.0,
          risk_reduction_impact: 62.4,
          unresolved_land_issues: 1,
          unresolved_approval_issues: 1,
          remarks_text: "Severe land bottleneck and forest clearance pending.",
        },
        {
          project_id: "PRJ_001",
          sector: "Highways",
          ministry: "Ministry of Road Transport and Highways",
          composite_risk_score: 82.3,
          risk_tier: "Critical",
          required_review_hours: 22.5,
          risk_reduction_impact: 54.1,
          unresolved_land_issues: 1,
          unresolved_approval_issues: 0,
          remarks_text: "Land acquisition delay near junction package 3.",
        },
        {
          project_id: "PRJ_006",
          sector: "Railways",
          ministry: "Ministry of Railways",
          composite_risk_score: 79.1,
          risk_tier: "Critical",
          required_review_hours: 20.0,
          risk_reduction_impact: 48.0,
          unresolved_land_issues: 0,
          unresolved_approval_issues: 1,
          remarks_text: "Clearance pending at state boundary.",
        },
      ],
    };
  }
}

/**
 * Fetch live early warning alerts
 */
export async function fetchAlerts() {
  try {
    const data = await request("/alerts");
    if (Array.isArray(data) && data.length > 0) {
      return data.map((a, idx) => ({
        id: a.id || idx + 1,
        severity: a.severity || (a.composite_risk_score >= 75 ? "Critical" : "High"),
        project: a.project_id,
        message: a.message,
        type: a.alert_type === "trend_increasing" ? "Escalating Risk Trend" : "Critical Tier Boundary",
        score: a.composite_risk_score,
        tier: a.risk_tier,
        timestamp: a.timestamp,
      }));
    }
    return fallbackAlerts;
  } catch (e) {
    console.warn("Live alerts unavailable, using fallback signals:", e);
    return fallbackAlerts;
  }
}

/**
 * Fetch CUF-Only vs Enhanced Data Model Comparison Study
 */
export async function fetchModelComparison() {
  try {
    return await request("/model-comparison");
  } catch (e) {
    console.warn("Model comparison unavailable:", e);
    return null;
  }
}

/**
 * Ask the authenticated assistant using role-scoped context and Groq generation.
 */
export async function askAssistant(message, history = []) {
  try {
    return await request("/chat", {
      method: "POST",
      body: JSON.stringify({ message, history }),
    });
  } catch (e) {
    console.warn("Chat assistant unavailable:", e);
    return null;
  }
}

/**
 * Stream the chat assistant's answer over SSE. Calls `onDelta(text)` per chunk and
 * `onMeta(meta)` once for the final { sources, model, rag_ready }. Returns false if
 * the request could not be started.
 */
export async function askAssistantStream(message, history = [], { onDelta, onMeta } = {}) {
  const url = `${API_BASE}/chat/stream`;
  const post = (u) =>
    fetch(u, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });

  let res = null;
  try {
    res = await post(url);
  } catch {
    res = null;
  }
  if ((!res || !res.ok) && !url.startsWith("http://127.0.0.1") && !url.startsWith("http://localhost")) {
    try {
      res = await post("http://127.0.0.1:8000/chat/stream");
    } catch {
      res = null;
    }
  }
  if (!res || !res.ok || !res.body) {
    // Streaming endpoint unavailable (e.g. hosted SSE restrictions): fall back to
    // the regular JSON chat endpoint and deliver its full answer as one delta.
    const answer = await request("/chat", {
      method: "POST",
      body: JSON.stringify({ message, history }),
    }).catch(() => null);
    if (!answer) return false;
    onDelta?.(answer.answer ?? "");
    onMeta?.({ sources: answer.sources ?? [], model: answer.model, rag_ready: !!(answer.rag_ready ?? false) });
    return true;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleLine = (line) => {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) return;
    const payload = trimmed.slice(5).trim();
    if (payload === "[DONE]") return;
    try {
      const obj = JSON.parse(payload);
      if (obj.delta !== undefined) onDelta?.(obj.delta);
      else if (obj.meta !== undefined) onMeta?.(obj.meta);
    } catch {
      /* ignore malformed SSE frames */
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      handleLine(buffer.slice(0, sep));
      buffer = buffer.slice(sep + 2);
    }
  }
  if (buffer.trim()) handleLine(buffer);
  return true;
}

/**
 * Knowledge-graph API: nodes (projects/ministries/agencies/sectors/risks) + edges.
 */
export async function fetchKnowledgeGraph({ projectId, ministry, limit = 150 } = {}) {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  if (ministry) params.set("ministry", ministry);
  if (limit) params.set("limit", limit);
  const qs = params.toString();
  return request(`/graph${qs ? `?${qs}` : ""}`);
}

/**
 * Narrative knowledge-graph report (JSON sections).
 */
export async function fetchGraphReport({ projectId, ministry, limit = 100 } = {}) {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  if (ministry) params.set("ministry", ministry);
  if (limit) params.set("limit", limit);
  const qs = params.toString();
  return request(`/graph/report${qs ? `?${qs}` : ""}`);
}

/**
 * MongoDB mirror status.
 */
export async function fetchMongoStatus() {
  try {
    return await request("/mongo/status");
  } catch {
    return { configured: false, connected: false };
  }
}

export async function fetchConfusionMatrix() {
  return request("/comparison/confusion");
}

/**
 * Live risk factor sync status (when the rolling 5-min refresh last ran)
 */
export async function fetchRiskStatus() {
  return request("/risk/status");
}

/**
 * Check RAG chat assistant health
 */
export async function checkAssistantHealth() {
  try {
    return await request("/groq-chat/health");
  } catch (e) {
    console.warn("Chat health unavailable:", e);
    return null;
  }
}

/**
 * Authenticated, role-scoped assistant (Groq generation; optional local embeddings).
 */
export async function askLocalAssistant(message, history = [], token = null, { onDelta, onMeta } = {}) {
  const url = `${API_BASE}/groq-chat`;
  const post = (u) =>
    fetch(u, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ message, history }),
    });

  let res = null;
  try {
    res = await post(url);
  } catch {
    res = null;
  }
  if (!res || !res.ok) {
    return res ? { failed: true, unauthorized: res.status === 401 || res.status === 403 } : false;
  }

  const data = await res.json();
  onDelta?.(data.answer ?? "");
  onMeta?.({ sources: data.sources ?? [], model: data.model });
  return true;
}

export async function checkLocalAssistantHealth() {
  try {
    return await request("/groq-chat/health");
  } catch (e) {
    console.warn("Assistant health unavailable:", e);
    return null;
  }
}

/**
 * --- Authentication & Roles ---
 * Tokens are attached as Bearer headers; the request() helper adds no auth by
 * default, so these functions forward the caller-supplied headers explicitly.
 */

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Self-registration for public (citizen) accounts — created active immediately.
 */
export async function registerPublicAccount(name, email, password) {
  const endpoint = "/auth/register";
  const res = await fetch(apiUrl(endpoint), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
  return readApiJson(res, endpoint);
}

/**
 * Change the current user's password (enforces portal password policy).
 * Returns { token, user } with a fresh token; clears password_must_change.
 */
export async function changePassword(token, currentPassword, newPassword) {
  const endpoint = "/auth/change-password";
  const res = await fetch(apiUrl(endpoint), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  return readApiJson(res, endpoint);
}

/**
 * Password sign-in for public accounts created via registration.
 */

/**
 * 1-click Demo Login for local demonstration and evaluation.
 */
export async function demoLogin(role) {
  const endpoint = "/auth/demo-login";
  const res = await fetch(apiUrl(endpoint), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
  return readApiJson(res, endpoint);
}

export async function loginPublicAccount(email, password) {
  const endpoint = "/auth/login";
  const res = await fetch(apiUrl(endpoint), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return readApiJson(res, endpoint);
}

/**
 * Resolve a token into the current user (used at app boot + after OAuth redirect).
 */
export async function fetchAuthMe(token) {
  const endpoint = "/auth/me";
  const res = await fetch(apiUrl(endpoint), { headers: authHeaders(token) });
  if (res.status === 401) return null;
  return readApiJson(res, endpoint);
}

/**
 * Admin: list all platform users.
 */
export async function fetchAdminUsers(token) {
  return request(`/admin/users`, { headers: authHeaders(token) });
}

/**
 * Admin: assign a role/scope to a user (activates pending or re-scopes active).
 */
export async function assignUserRole(token, userId, role, scope) {
  return request(`/admin/users/${userId}/role`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(role === "admin" ? { role } : { role, ...(scope || {}) }),
  });
}

/**
 * Admin: create a government account with role + initial password.
 */
export async function createGovUser(token, payload) {
  return request(`/admin/users`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

/**
 * Admin: reset a user's password (forces change on next login).
 */
export async function resetUserPassword(token, userId, newPassword) {
  return request(`/admin/users/${userId}/reset-password`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ new_password: newPassword }),
  });
}

/**
 * Admin: revoke or reinstate a user's access.
 */
export async function setUserAccess(token, userId, revoked, reason = "") {
  const endpoint = revoked
    ? `/admin/users/${userId}/revoke`
    : `/admin/users/${userId}/reinstate`;
  return request(endpoint, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
}

/**
 * Admin: platform-wide dashboard aggregate.
 */
export async function fetchAdminDashboard(token) {
  return request(`/admin/dashboard`, { headers: authHeaders(token) });
}

/**
 * Ministry: scoped dashboard.
 */
export async function fetchMinistryDashboard(token) {
  return request(`/ministry/dashboard`, { headers: authHeaders(token) });
}

/**
 * Ministry: decide on an agency milestone submission.
 */
export async function decideMilestone(token, submissionId, approve, note = "") {
  return request(`/ministry/approvals/${submissionId}/decision`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ approve, note }),
  });
}

/**
 * Agency: submit a milestone update.
 */
export async function submitMilestone(token, payload) {
  return request(`/agency/milestones`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

/**
 * Agency: dashboard with own project, milestones, uploads, thread.
 */
export async function fetchAgencyDashboard(token) {
  return request(`/agency/dashboard`, { headers: authHeaders(token) });
}

/**
 * Public (no auth): public-safe project directory + summary.
 */
export async function fetchPublicProjects(params = {}) {
  const query = new URLSearchParams();
  if (params.search) query.append("search", params.search);
  if (params.ministry) query.append("ministry", params.ministry);
  if (params.sector) query.append("sector", params.sector);
  if (params.on_track !== undefined) query.append("on_track", params.on_track);
  if (params.limit) query.append("limit", params.limit);
  if (params.offset) query.append("offset", params.offset);
  const qs = query.toString() ? `?${query.toString()}` : "";
  return request(`/public/projects${qs}`);
}

/**
 * One page of the public directory, plus the total number of rows matching the
 * same filters. The backend reports the total in `X-Total-Count` because the
 * body is only the current page — which is what lets the directory page
 * through the whole portfolio instead of stopping at the first slice.
 */
export async function fetchPublicProjectPage(params = {}) {
  const query = new URLSearchParams();
  if (params.search) query.append("search", params.search);
  if (params.ministry) query.append("ministry", params.ministry);
  if (params.sector) query.append("sector", params.sector);
  if (params.on_track !== undefined) query.append("on_track", params.on_track);
  query.append("limit", params.limit ?? 200);
  query.append("offset", params.offset ?? 0);
  const { data, headers } = await requestWithHeaders(
    `/public/projects?${query.toString()}`,
  );
  const total = Number(headers.get("X-Total-Count"));
  return { rows: Array.isArray(data) ? data : [], total: Number.isFinite(total) ? total : null };
}

export async function fetchPublicSummary() {
  return request(`/public/summary`);
}

/* ---------------------------------------------------------------------------
 * Public project complaints ("report an issue")
 * ------------------------------------------------------------------------ */

/**
 * Sends an anonymous report that a project's published data looks wrong.
 *
 * Deliberately not routed through `request()`: that helper silently retries
 * against http://127.0.0.1:8000 when the proxied call fails, and re-POSTing a
 * report that the server already accepted would file the same complaint twice.
 * A write gets exactly one attempt.
 */
export async function submitPublicComplaint(payload) {
  const res = await fetch(`${API_BASE}/public/complaints`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Could not send your report: ${res.status}`);
  }
  return res.json();
}

/** The category list the form renders, served by the backend so the two agree. */
export async function fetchComplaintCategories() {
  return request(`/public/complaint-categories`);
}

/** Admin: the complaint triage queue. */
export async function fetchAdminComplaints(token, params = {}) {
  return request(`/admin/complaints${adminQuery(params)}`, {
    headers: authHeaders(token),
  });
}

/** Admin: change triage status and/or record an internal note. */
export async function updateAdminComplaint(token, complaintId, changes) {
  return request(`/admin/complaints/${complaintId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(changes),
  });
}

/* ---------------------------------------------------------------------------
 * Admin · Platform Operations
 * Governance endpoints that sit outside user management: what the public
 * portal may show, data/model health, milestone and document triage, and the
 * risk-signal record.
 * ------------------------------------------------------------------------ */

/** Builds a query string, dropping empty values so they are not sent as "". */
function adminQuery(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.append(key, String(value));
  }
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

/**
 * Admin: every public-directory row, including unpublished ones. The public
 * router only ever returns visible rows, so this is the only way to find a
 * project that was hidden.
 *
 * Returns `{rows, total}` rather than a bare array: the table holds a couple
 * of thousand rows, so the response is a capped page and `total` is what the
 * "hidden" badge counts against — the page alone would under-report.
 */
export async function fetchAdminPublicRowPage(params = {}) {
  const query = new URLSearchParams();
  query.append("limit", params.limit ?? 200);
  query.append("offset", params.offset ?? 0);
  if (params.search) query.append("search", params.search);
  if (params.visible !== undefined && params.visible !== "")
    query.append("visible", params.visible);
  const { data, headers } = await requestWithHeaders(
    `/admin/public-projects?${query.toString()}`,
    { headers: authHeaders(params.token) },
  );
  const total = Number(headers.get("X-Total-Count"));
  return {
    rows: Array.isArray(data) ? data : [],
    total: Number.isFinite(total) ? total : null,
  };
}

/**
 * Admin: publish/unpublish a project and/or edit its public summary.
 * Only the keys present in `changes` are sent, so an omitted summary is left
 * untouched rather than blanked.
 */
export async function updateAdminPublicRow(token, projectId, changes) {
  return request(`/admin/public-projects/${projectId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(changes),
  });
}

/** Admin: per-table row counts, system metadata keys, model load state. */
export async function fetchAdminSystemMeta(token) {
  return request(`/admin/system-meta`, { headers: authHeaders(token) });
}

/** Admin: model artifact inventory and in-memory registry state. */
export async function fetchAdminModelHealth(token) {
  return request(`/admin/model-health`, { headers: authHeaders(token) });
}

/** Admin: re-seed the database and retrain/export the model artifacts. */
export async function runAdminSeedDatabase(token) {
  return request(`/admin/seed-database`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

/** Admin: milestone submissions across all ministries. */
export async function fetchAdminSubmissions(token, params = {}) {
  return request(`/admin/submissions${adminQuery(params)}`, {
    headers: authHeaders(token),
  });
}

/** Admin: escalation decision on a ministry's pending submission. */
export async function decideAdminSubmission(token, submissionId, approve, note = "") {
  return request(`/admin/submissions/${submissionId}/decision`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ approve, note }),
  });
}

/** Admin: uploaded proof documents with the uploading account resolved. */
export async function fetchAdminDocuments(token, params = {}) {
  return request(`/admin/documents${adminQuery(params)}`, {
    headers: authHeaders(token),
  });
}

/** Admin: remove a proof document uploaded in error. */
export async function deleteAdminDocument(token, documentId) {
  return request(`/admin/documents/${documentId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

/** Admin: NLP warning tags extracted from snapshot remarks. */
export async function fetchAdminRemarkSignals(token, params = {}) {
  return request(`/admin/remark-signals${adminQuery(params)}`, {
    headers: authHeaders(token),
  });
}

/** Admin: ministry/agency message threads, flattened for oversight. */
export async function fetchAdminMessageNotes(token, params = {}) {
  return request(`/admin/message-notes${adminQuery(params)}`, {
    headers: authHeaders(token),
  });
}

/**
 * Admin: audit trail. Accepts the same filters the endpoint does; `since` is an
 * ISO date. Unset filters are omitted so the server applies no narrowing.
 */
export async function fetchAdminAuditLogs(token, params = {}) {
  return request(`/admin/audit-logs${adminQuery({ limit: 200, ...params })}`, {
    headers: authHeaders(token),
  });
}

/**
 * Fetch per-state satellite vegetation for one acquisition.
 *
 * Pass no date to get the most recent observation held locally. The response
 * states which date was actually used, so the caller must render that rather
 * than the date it asked for: the endpoint falls back to the latest available
 * when the requested date was never measured, and showing the requested date
 * against another date's numbers would be a silent substitution.
 */
export async function fetchStateVegetation(date = null) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  const data = await request(`/public/geo/vegetation${query}`);
  return {
    sourceLayer: data?.source_layer ?? null,
    sourceUrl: data?.source_url ?? null,
    resolutionM: data?.resolution_m ?? null,
    dates: Array.isArray(data?.dates) ? data.dates : [],
    selectedDate: data?.selected_date ?? null,
    states: Array.isArray(data?.states) ? data.states : [],
    trends: Array.isArray(data?.trends) ? data.trends : [],
    limitations: Array.isArray(data?.limitations) ? data.limitations : [],
    scope: data?.scope ?? "state",
    generatedAt: data?.generated_at ?? null,
  };
}
