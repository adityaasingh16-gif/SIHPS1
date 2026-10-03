import { translate } from "../i18n";

export { riskColor, riskBg, riskLabel, riskTierKey, priorityScore, RISK_TIER_CHART_COLORS };


function riskColor(risk) {
 if (risk >= 75) return"text-risk-critical";
 if (risk >= 50) return"text-risk-high";
 if (risk >= 30) return"text-risk-medium";
 return"text-risk-low";
}


function riskBg(risk) {
 if (risk >= 75) return"bg-risk-critical-subtle border-risk-critical-border";
 if (risk >= 50) return"bg-risk-high-subtle border-risk-high-border";
 if (risk >= 30) return"bg-risk-medium-subtle border-risk-medium-border";
 return"bg-risk-low-subtle border-risk-low-border";
}


/**
 * Risk tier -> display label.
 *
 * `lang` is an argument rather than a module-level read so this stays a pure
 * function that chart maths and non-React callers can use. Pass the active
 * language in, or use `useRiskLabel()` from a component.
 *
 * Only the displayed text is translated. The tier names returned by the
 * upstream `severity` fields are data values used for equality checks, so they
 * must stay in English everywhere else.
 */
function riskLabel(risk, lang = "en") {
 return translate(lang, riskTierKey(risk));
}


/**
 * Risk tier -> the catalogue key for that tier.
 *
 * Filters and sort state hold this key rather than the rendered label, so
 * switching language cannot silently change which rows a filter matches.
 */
function riskTierKey(risk) {
 if (risk >= 75) return "common.critical";
 if (risk >= 50) return "common.high";
 if (risk >= 30) return "common.medium";
 return "common.low";
}


/**
 * Risk tier -> chart colour. Ordered Low -> Critical to match the order
 * `priorityData` is built in, and read from tokens so the pie inverts with
 * the theme instead of staying light-mode hardcoded.
 */
const RISK_TIER_CHART_COLORS = [
  "var(--risk-low)",
  "var(--risk-medium)",
  "var(--risk-high)",
  "var(--risk-critical)",
];


/**
 * One number for "which project needs attention first".
 *
 * The three signals are already 0-100 percentages, so they combine directly.
 * Overall risk carries half the weight because it is the model's own
 * estimate; cost and schedule overrun split the rest. The result is used only
 * for ordering, so the weighting is a ranking policy rather than a claim about
 * the true severity of a project.
 */
function priorityScore(project) {
  if (!project) return 0;
  const risk = Number(project.risk) || 0;
  const cost = Number(project.costRisk) || 0;
  const time = Number(project.timeRisk) || 0;
  return 0.5 * risk + 0.25 * cost + 0.25 * time;
}
