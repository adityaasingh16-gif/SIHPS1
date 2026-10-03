import { translate } from "../i18n";

export { FEATURE_LABELS, getFeatureInfo };

/**
 * Raw feature name -> catalogue key.
 *
 * Values stay as the upstream snake_case names so they keep matching what the
 * ML service returns. Only the display label is translated, via the catalogue.
 */
const FEATURE_KEYS = {
  progress_gap: "feature.progress_gap",
  remarks_warning_count: "feature.remarks_warning_count",
  original_cost: "feature.original_cost",
  exp_burn_ratio: "feature.exp_burn_ratio",
  unresolved_land_issues: "feature.unresolved_land_issues",
  unresolved_approval_issues: "feature.unresolved_approval_issues",
  schedule_slippage_ratio: "feature.schedule_slippage_ratio",
  cost_risk_pct: "feature.cost_risk_pct",
  contractor_delay_events: "feature.contractor_delay_events",
  time_elapsed_ratio: "feature.time_elapsed_ratio",
  cumulative_cost_ratio: "feature.cumulative_cost_ratio",
  financial_progress_pct: "feature.financial_progress_pct",
  physical_progress_pct: "feature.physical_progress_pct",
  milestone_achievement_ratio: "feature.milestone_achievement_ratio",
  monsoon_impact_flag: "feature.monsoon_impact_flag",
};

/**
 * English fallback labels, kept for the handful of callers that read this map
 * directly instead of going through `getFeatureInfo`.
 */
const FEATURE_LABELS = Object.fromEntries(
  Object.entries(FEATURE_KEYS).map(([name, key]) => [name, translate("en", key)]),
);

/**
 * Display label for a SHAP driver.
 *
 * `lang` is an argument rather than a module-level read so this stays a pure
 * function that non-React callers can use. Pass the active language in, or
 * read it from a component that already has one.
 *
 * An unrecognised `sector_*` feature is a measured exposure, not prose, so the
 * sector name itself is left as-is and only the prefix is translated.
 */
function getFeatureInfo(item, lang = "en") {
  if (!item) {
    return {
      label: translate(lang, "feature.general"),
      value: 0,
      formatted: translate(lang, "modal.pts", { sign: "+", n: "0.0" }),
      widthPct: 10,
      isMitigating: false,
    };
  }

  const rawName = item.feature_name || item.factor_name || item.name;
  let label;
  if (rawName && FEATURE_KEYS[rawName]) {
    label = translate(lang, FEATURE_KEYS[rawName]);
  } else if (rawName && rawName.startsWith("sector_")) {
    label = translate(lang, "feature.sectorExposure", { name: rawName.slice(7) });
  } else {
    label = translate(lang, "feature.riskMetric");
  }

  const rawVal = Number(item.shap_value ?? item.impact_value ?? item.value ?? 0);
  const numVal = isNaN(rawVal) ? 0 : rawVal;
  const isMitigating = item.direction ==="decreases_risk" || numVal < 0;
  const sign = isMitigating ?"-" :"+";
  const absVal = Math.abs(numVal);
  const displayPts = absVal < 1.0 ? (absVal * 10).toFixed(1) : absVal.toFixed(1);
  const formatted = translate(lang, "modal.pts", { sign, n: displayPts });
  const widthPct = Math.min(100, Math.max(12, Math.round(absVal > 2 ? absVal * 4 : absVal * 80)));

  return { label, value: numVal, formatted, widthPct, isMitigating };
}
