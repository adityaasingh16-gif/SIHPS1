import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export const PreferencesContext = createContext(null);

const THEME_KEY = "dhrishti-theme";
const LANG_KEY = "dhrishti-lang";

function readStored(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    // Private-mode / storage-disabled browsers: fall back silently.
    return fallback;
  }
}

function writeStored(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}

/**
 * Theme and language, owned in one place.
 *
 * These were previously two independent `useState` hooks in the App
 * component. Once the shell moved into its own module, calling the hook in
 * both places created two separate copies of the same preference, so a
 * language change made in the topbar could leave the value used by the login
 * and public screens stale. A context keeps one source of truth.
 */
export function PreferencesProvider({ children }) {
  const [dark, setDark] = useState(() => readStored(THEME_KEY) === "dark");
  const [language, setLanguage] = useState(() => readStored(LANG_KEY, "en"));

  // Dark mode is applied by toggling a class on <html>. Every colour in the
  // app resolves through semantic tokens, so no component needs to know
  // which theme is active.
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    writeStored(THEME_KEY, dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    writeStored(LANG_KEY, language);
  }, [language]);

  const toggleTheme = useCallback(() => setDark((d) => !d), []);

  return (
    <PreferencesContext.Provider value={{ dark, setDark, toggleTheme, language, setLanguage }}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function useTheme() {
  const { dark, setDark, toggleTheme } = usePreferences();
  return { dark, setDark, toggleTheme };
}

export function useLanguage() {
  const { language, setLanguage } = usePreferences();
  return { language, setLanguage };
}

export function usePreferences() {
  const ctx = useContext(PreferencesContext);
  if (!ctx) {
    throw new Error("usePreferences must be used inside <PreferencesProvider>");
  }
  return ctx;
}

/**
 * Pins a subtree to English without touching the stored preference.
 *
 * The role workspaces (admin, ministry, agency) are English-only surfaces.
 * Without this, an officer who picked Hindi on the dashboard would land on a
 * Hindi sidebar wrapped around an English-only panel. Scoping the subtree keeps
 * that screen internally consistent, and because nothing here writes to
 * localStorage, their language choice is still in force on every other route.
 */
export function EnglishOnlyScope({ children }) {
  const prefs = usePreferences();
  const scoped = useMemo(
    () => ({ ...prefs, language: "en", setLanguage: () => {} }),
    [prefs],
  );
  return (
    <PreferencesContext.Provider value={scoped}>{children}</PreferencesContext.Provider>
  );
}
