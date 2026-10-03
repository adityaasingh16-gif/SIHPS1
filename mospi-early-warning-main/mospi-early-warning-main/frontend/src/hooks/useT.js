import { useCallback, useContext } from "react";

import { translate } from "../i18n";
import { PreferencesContext } from "./usePreferences";

/**
 * The active language code, or "en" outside a provider.
 *
 * Split out from `useT()` because a few helpers need the code itself rather
 * than a bound translator -- `riskLabel(risk, lang)`, for instance, is a pure
 * function that also gets called from chart code.
 */
export function useLocale() {
  const ctx = useContext(PreferencesContext);
  // No provider in scope (a test, a story): fall through to English.
  return ctx ? ctx.language : "en";
}

/**
 * Returns a translator bound to the active language.
 *
 * Pages that already receive `t` as a prop keep using it. This hook exists for
 * the deep child components -- chart legends, map overlays, table headers --
 * that were previously hard-coded English and would otherwise need a `t` prop
 * threaded through several layers of card and panel wrappers.
 *
 * It degrades to English rather than throwing when used outside a provider, so
 * a component can be rendered in isolation (a test, a story) without a
 * PreferencesProvider wrapper.
 */
export function useT() {
  const language = useLocale();
  return useCallback(
    (key, vars) => translate(language, key, vars),
    [language],
  );
}
