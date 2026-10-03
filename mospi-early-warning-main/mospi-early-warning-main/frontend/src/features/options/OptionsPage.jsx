import { useMemo } from "react";
import { Database, Globe, Info, Moon, Settings2, Sun } from "lucide-react";

import { LANGUAGES, translate } from "../../i18n";
import { useLanguage, useTheme } from "../../hooks/usePreferences";
import { usePublicSession } from "../../PublicSession";
import { PageHeader } from "../../components/ui/PageHeader";

/**
 * Read-only options surface.
 *
 * There is deliberately nothing here that writes to the server. Theme and
 * language are the only settings the product has, and both live in
 * `localStorage` via `usePreferences`, so they work identically for an
 * anonymous visitor and a signed-in officer.
 */
export function OptionsPage() {
  const { dark, toggleTheme } = useTheme();
  const { language, setLanguage } = useLanguage();
  const { onLogin, loggedInUser } = usePublicSession();

  const t = useMemo(() => (key) => translate(language, key), [language]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Settings2}
        title={t("public.options")}
        subtitle={t("options.subtitle")}
      />

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Appearance */}
        <section className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
          <h3 className="flex items-center gap-2 text-sm font-bold text-fg">
            <Sun size={16} className="text-brand-hover" />
            {t("public.appearance")}
          </h3>

          <div className="mt-4 flex items-center justify-between gap-4 rounded-xl border border-line bg-page p-4">
            <div className="flex items-center gap-3">
              {dark ? (
                <Moon size={18} className="text-fg-3" />
              ) : (
                <Sun size={18} className="text-fg-3" />
              )}
              <div>
                <p className="text-sm font-semibold text-fg">
                  {dark ? t("options.theme.dark") : t("options.theme.light")}
                </p>
                <p className="text-xs text-fg-3">{t("options.theme.applied")}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={toggleTheme}
              className="shrink-0 rounded-lg border border-line-strong px-4 py-2 text-xs font-bold uppercase tracking-wider text-fg-2 transition hover:bg-hover"
            >
              {dark ? t("options.theme.useLight") : t("options.theme.useDark")}
            </button>
          </div>
        </section>

        {/* Language */}
        <section className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
          <h3 className="flex items-center gap-2 text-sm font-bold text-fg">
            <Globe size={16} className="text-brand-hover" />
            {t("language")}
          </h3>

          <div className="mt-4 rounded-xl border border-line bg-page p-4">
            <label
              htmlFor="options-language"
              className="text-xs font-bold uppercase tracking-wider text-fg-3"
            >
              {t("options.languageLabel")}
            </label>
            <select
              id="options-language"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="mt-2 w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-sm text-fg outline-none focus:border-brand"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.native} — {l.english}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-fg-4">
              {t("options.languageNote")}
            </p>
          </div>
        </section>

        {/* Access level */}
        <section className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
          <h3 className="flex items-center gap-2 text-sm font-bold text-fg">
            <Info size={16} className="text-brand-hover" />
            {t("options.accessTitle")}
          </h3>

          <div className="mt-4 rounded-xl border border-line bg-page p-4">
            <p className="text-sm font-semibold text-fg">
              {loggedInUser
                ? t("options.signedInAs", {
                    name: loggedInUser.name || loggedInUser.email,
                  })
                : t("options.publicAccess")}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-fg-3">
              {t("options.accessNote")}
            </p>
            {!loggedInUser && onLogin && (
              <button
                type="button"
                onClick={onLogin}
                className="mt-4 rounded-full bg-brand px-5 py-2.5 text-[11px] font-bold uppercase tracking-wider text-brand-fg transition hover:opacity-90"
              >
                {t("options.signIn")}
              </button>
            )}
          </div>
        </section>

        {/* Data provenance */}
        <section className="rounded-2xl border border-line bg-raised p-5 shadow-sm">
          <h3 className="flex items-center gap-2 text-sm font-bold text-fg">
            <Database size={16} className="text-brand-hover" />
            {t("options.provenanceTitle")}
          </h3>

          <dl className="mt-4 space-y-2.5 text-xs">
            {[
              ["options.prov.scope", "options.prov.scopeValue"],
              ["options.prov.signals", "options.prov.signalsValue"],
              ["options.prov.models", "options.prov.modelsValue"],
              ["options.prov.allocation", "options.prov.allocationValue"],
              ["options.prov.assistant", "options.prov.assistantValue"],
            ].map(([k, v]) => (
              <div
                key={k}
                className="flex flex-col gap-0.5 border-b border-line pb-2 last:border-0 sm:flex-row sm:gap-4"
              >
                <dt className="shrink-0 font-bold uppercase tracking-wider text-fg-3 sm:w-28">
                  {t(k)}
                </dt>
                <dd className="text-fg-2">{t(v)}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </div>
  );
}
