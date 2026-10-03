import { useCallback } from "react";

import { riskLabel } from "../lib/risk";
import { useLocale } from "./useT";

/**
 * Locale-aware `riskLabel` for components.
 *
 * `riskLabel` itself stays a pure `(risk, lang)` function because it is also
 * called from chart code and from non-React helpers; this hook is the ergonomic
 * wrapper that reads the active language from context.
 */
export function useRiskLabel() {
  const lang = useLocale();
  return useCallback((risk) => riskLabel(risk, lang), [lang]);
}
